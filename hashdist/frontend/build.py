from .stack_dsl import parse_stack_dsl, evaluate_dict_with_conditions, Match, Select, IllegalStackSpecError
from .query import normalize_cfg_vars, query_attrs

from ..core import BuildStore, SourceCache, DiskCache, BuildSpec
from ..core.utils import substitute
from ..core.hasher import Hasher

import os
from os.path import join as pjoin
import imp
import sys

from pprint import pprint, pformat

from functools import wraps

def search_phase(pipeline, needle):
    for i, (name, _, _) in enumerate(pipeline):
        if name == needle:
            return i
    raise ValueError('%s not in pipeline list' % needle)

def add_pipeline_stage(pipeline, after, before, name, func, when):
    needle, offset = (before, 0) if before is not None else (after, 1)
    i = search_phase(pipeline, needle)
    pipeline.insert(i + offset, (name, func, when))

def run_pipeline(pipeline, *args):
    for name, func, when in pipeline:
        if func is not None:
            if when is None or when(*args):
                func(*args)
    
class Pipeline(object):
    def __init__(self):
        # gathers registrations from add_assemble_stage:
        self.assemble_pipeline_registrations = []
        self._assemble_pipeline = None

    def merge(self, other):
        if not isinstance(other, Pipeline):
            raise TypeError()
        self.assemble_pipeline_registrations.extend(other.assemble_pipeline_registrations)
        self._assemble_pipeline = None

    def copy(self):
        p = Pipeline()
        p.merge(self)
        return p

    def get_assemble_pipeline(self):
        if self._assemble_pipeline is not None:
            return self._assemble_pipeline
        else:
            self._assemble_pipeline = pipeline = [
                ('assemble_start', None, None),
                ('recipes', None, None),
                ('recipes_profile_install', None, None),
                ('post_recipes', None, None),
                ('assemble_end', None, None),
                ]
            for after, before, name, func, when in self.assemble_pipeline_registrations:
                add_pipeline_stage(pipeline, after, before, name, func, when)
            return pipeline

    def add_assemble_stage(self, after=None, before=None, name=None, func=None, when=None):
        if int(after is None) + int(before is None) != 1:
            raise TypeError('must specify either after or before')

        if func is None:
            def decorator(func):
                self.add_assemble_stage(after, before, name, func, when)
                return func
            # return partially applied function
            return decorator
        else:
            if name is None:
                name = func.__name__
            self.assemble_pipeline_registrations.append((after, before, name, func, when))
            self._assemble_pipeline = None # need to re-assemble after this

    def add_recipe(self, recipe_name, func=None, name=None):
        def should_run(ctx, pkg, build_spec):
            return pkg['recipe'] == recipe_name
        return self.add_assemble_stage(after='recipes', func=func, name=name, when=should_run)

    def assemble_build_spec(self, *args):
        run_pipeline(self.get_assemble_pipeline(), *args)

class StackBuildContext(object):
    def __init__(self, pipeline, logger, cache, build_store, source_cache, artifact_id_map):
        self.pipeline = pipeline
        self.logger = logger
        self.cache = cache
        self.build_store = build_store
        self.source_cache = source_cache
        self.artifact_id_map = artifact_id_map
        #self.stack_spec = stack_spec

    def get_artifact_id(self, pkg):
        return self.artifact_id_map[pkg]

    def configure(self, package_cfg, package_attrs):
        self.pipeline.run_configuration(self, package_cfg, package_attrs)
       
    def query_build_spec(self, package_attrs):
        package_build_spec = {
            "build": {
                "script": [],
                "import": [],
                "env": {},
                "env_nohash": {}},
            "files": [],
            "sources": [],
            "name": package_attrs['package'],
            "version": 'n' # for now
            }

        self.pipeline.assemble_build_spec(self, package_attrs, package_build_spec)
        return package_build_spec
        
## @pipeline.add_configuration_stage(after='configuration_start')
## def find_possible_versions(ctx, cfg, attrs):
##     """
##     Auto-detect cfg['possible_versions'] (if neither
##     'possible_versions' nor 'version' is given) by scanning the
##     conditionals in the stack spec for the current package.
##     """
##     if 'possible_versions' not in cfg and 'version' not in cfg:
##         result = []
##         for attrname, select in ctx.stack_spec['build'].items():
##             for condition, value in select.options:
##                 c = condition.partial_satisfy(cfg)
##                 if isinstance(c, Match) and c.varname == 'version':
##                     result.extend(c.get_mentioned_values())
##         cfg['possible_versions'] = result

## @pipeline.add_configuration_stage(after='find_possible_versions')
## def decide_version(ctx, cfg, attrs):
##     if 'version' not in cfg:
##         if 'possible_versions' in cfg and len(cfg['possible_versions']) == 1:
##             cfg['version'] = cfg['possible_versions'][0]
##         else:
##             raise ValueError('Unable to decide on version for %s' % cfg['package'])

## @pipeline.add_configuration_stage(before='configuration_end')
## def evaluate_build_attrs(ctx, cfg, attrs):
##     add_attrs = evaluate_dict_with_conditions(ctx.stack_spec['build'], cfg)
##     for key, value in add_attrs.items():
##         if isinstance(value, basestring):
##             add_attrs[key] = substitute(value, cfg)
##     attrs.update(add_attrs)

def build_yaml_profile(config, logger, spec_dir, profile_name, cfg):

    stack_spec = parse_stack_dsl_file(spec_dir)

    ctx = StackBuildContext(pipeline,
                            logger=logger,
                            build_store=BuildStore.create_from_config(config, logger),
                            source_cache=SourceCache.create_from_config(config, logger),
                            cache=DiskCache.create_from_config(config, logger))

    # Strategy:
    # 1. Search for all debian: ...; these must not contain $..
    # 2. Update
    
    # 1. configuration, doing dfs to search for packages (roots in profile)
    #   Q: What if build_deps depends on version=?
    # 2. build tree where one can vary version... hmm...
    # 3. 

    
    profile_doc = evaluate_dict_with_conditions(stack_spec['profiles'][profile_name], cfg)
    for package, query in profile_doc.items():
        if query is None:
            query = {}
        if 'package' not in query:
            query['package'] = package

        package_cfg = dict(cfg)
        package_cfg.update(query)
        package_cfg = normalize_cfg_vars(package_cfg)

        attrs = {}
        ctx.configure(package_cfg, attrs)
        attrs['package'] = package_cfg['package']
        attrs['version'] = package_cfg['version']

        build_spec = ctx.query_build_spec(attrs)
        pprint( build_spec)

    #pprint( doc['build'])
    #pprint(profile_doc)


class Package(object):
    """
    The main purpose is to use the `__dict__` to store the attributes
    for a package (which should be considered freely modifiable during
    pipeline runs).
    
    """
    version = 'n'
    build_deps = ()

    def __init__(self, **attrs):
        self.build_deps = []
        self.soft_deps = []
        self.version = 'n'
        
        self.__dict__.update(attrs)
        # to avoid recursing through entire tree when doing __hash__ or __eq__,
        # compute a secure hash and export it in get_secure_hash() (which Hasher
        # will call)
        h = Hasher()
        h.update(attrs)
        self._secure_hash = h.digest()

    def get_secure_hash(self):
        return ("hashdist.frontend.Package", self._secure_hash)

    def __repr__(self):
        return ('Package(package=%r, build_deps=[%s], ...)' %
                (self.package, ', '.join([dep.package for dep in self.build_deps])))

    # compare/hash by attribute values
    def __hash__(self):
        return hash(self._secure_hash)

    def __eq__(self, other):
        return type(other) is Package and self._secure_hash == other._secure_hash

    def __ne__(self, other):
        return not self == other


def get_build_spec(ctx, package):
    """Runs through the pipeline to get a build spec for the package
    """
    # Set up initial build spec, including package name, version, and imports
#    pprint( artifact_id_map)
    imports = []
    for dep in package.build_deps:
        before = [ctx.get_artifact_id(sub_dep) for sub_dep in dep.build_deps]
        imports.append(dict(ref=dep.package.upper(), id=ctx.get_artifact_id(dep), before=before))
    package_build_spec = {
        "build": {
            "script": [],
            "import": imports,
            "env": {},
            "env_nohash": {}},
        "files": [],
        "sources": [],
        "name": package.package,
        "version": package.version,
        }
    d = dict(package.__dict__)
    del d['_secure_hash']
    ctx.pipeline.assemble_build_spec(ctx, d, package_build_spec)
    return BuildSpec(package_build_spec)

def build_packages(config, logger, pipeline, packages):
    """Build the given packages, which should be pre-processed and contain all attributes.

    The `build_deps`, `soft_deps` should be lists of references to other
    `Package` objects.

    `pipeline` is used to convert the package definitions to build specs
    """
    artifact_id_map = {}
    ctx = StackBuildContext(pipeline,
                            logger=logger,
                            build_store=BuildStore.create_from_config(config, logger),
                            source_cache=SourceCache.create_from_config(config, logger),
                            cache=DiskCache.create_from_config(config, logger),
                            artifact_id_map=artifact_id_map)
    jobs = [] # serial for now

    def depth_first_build(package):
        if package not in artifact_id_map:
            for dep in package.build_deps + package.soft_deps:
                depth_first_build(dep)
                assert dep in artifact_id_map

            print package, artifact_id_map
            build_spec = get_build_spec(ctx, package)
            jobs.append((package, build_spec))
            artifact_id_map[package] = build_spec.artifact_id

    for package in packages:
        depth_first_build(package)

    results = {}
    for pkg, job in jobs:
        results[pkg] = ctx.build_store.ensure_present(job, config, keep_build='error')
    return results

def build_profile(config, logger, filename, profile_name):
    stack_py = None
    if os.path.isdir(filename):
        if os.path.exists(pjoin(filename, 'stack.py')):
            stack_py = pjoin(filename, 'stack.py')
    elif filename.endswith('.py'):
        stack_py = filename
        
    with open(stack_py) as f:
        # The following causes __name__ == '__hdistspec__' inside the module...
        try:
            mod = imp.load_module('__hdistspec__', f, stack_py,
                                  ('.py', 'r', imp.PY_SOURCE))
        finally:
            try:
                del sys.modules['__hdistspec__']
            except KeyError:
                pass

    get_profile_spec = getattr(mod, 'get_profile_spec', None)
    if get_profile_spec is None:
        raise NotImplementedError()
    
    get_pipeline = getattr(mod, 'get_pipeline', None)
    if get_pipeline is None:
        def get_pipeline(config, logger):
            from .default_recipes import pipeline as default_pipeline
            p = default_pipeline.copy()
            mod_pipeline = getattr(mod, 'pipeline', None)
            if mod_pipeline:
                p.merge(mod_pipeline)
            return p

    pipeline = get_pipeline(config, logger)
    profile = get_profile_spec(config, logger, profile_name)
    build_packages(config, logger, pipeline, [profile])
