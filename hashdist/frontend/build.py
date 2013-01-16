from .parse_stack_spec import parse_stack_spec, evaluate_dict_with_conditions, Match, Select
from .query import normalize_cfg_vars, query_attrs

from ..core import BuildStore, SourceCache, DiskCache
from ..core.utils import substitute

from pprint import pprint

class StackBuildPipeline(object):
    def __init__(self):
        # [(phase_name, func)]
        # register some phase markers initially
        self.pipeline = [
            ('parse', None),
            ('configuration_start', None),
            ('configuration_end', None),
            ('recipes', None),
            ('recipes_profile_install', None),
            ('post_recipes', None),
            ('build', None)]

    def add_stage(self, after=None, before=None, name=None, func=None):
        if int(after is None) + int(before is None) != 1:
            raise TypeError('must specify either after or before')

        if func is None:
            def decorator(func):
                name_ = name
                if name_ is None:
                    name_ = func.__name__
                self.add_stage(after, before, name_, func)
                return func
            return decorator

        needle, offset = (before, 0) if before is not None else (after, 1)
        for i, (it_name, _) in enumerate(self.pipeline):
            if it_name == needle:
                self.pipeline.insert(i + offset, (name, func))
                break
        else:
            raise ValueError("Did not find pipeline stage %s" % needle)

    def add_recipe(self, func, name=None):
        self.add_stage(after='recipes', name=name, func=func)

    def run_pipeline(self, *args):
        for name, func in self.pipeline:
            if func is not None:
                func(*args)

class StackBuildContext(object):
    def __init__(self, pipeline, logger, cache, build_store, source_cache, stack_spec):
        self.pipeline = pipeline
        self.logger = logger
        self.cache = cache
        self.build_store = build_store
        self.source_cache = source_cache
        self.stack_spec = stack_spec
        
    def query_build_spec(self, package_cfg):
        package_attrs = {}
        package_build_spec = {}
        pipeline.run_pipeline(ctx, package_cfg, package_attrs, package_build_spec)
        

     
pipeline = StackBuildPipeline()
from .default_recipes import register_recipes
register_recipes(pipeline)
del register_recipes

@pipeline.add_stage(after='configuration_start')
def find_possible_versions(ctx, cfg, attrs, build_spec):
    """
    Auto-detect cfg['possible_versions'] (if neither
    'possible_versions' nor 'version' is given) by scanning the
    conditionals in the stack spec for the current package.
    """
    if 'possible_versions' not in cfg and 'version' not in cfg:
        result = []
        for attrname, select in ctx.stack_spec['build'].items():
            for condition, value in select.options:
                c = condition.partial_satisfy(cfg)
                if isinstance(c, Match) and c.varname == 'version':
                    result.extend(c.get_mentioned_values())
        cfg['possible_versions'] = result

@pipeline.add_stage(after='find_possible_versions')
def decide_version(ctx, cfg, attrs, build_spec):
    if 'version' not in cfg:
        if 'possible_versions' in cfg and len(cfg['possible_versions']) == 1:
            cfg['version'] = cfg['possible_versions'][0]
        else:
            raise ValueError('Unable to decide on version for %s' % cfg['package'])

@pipeline.add_stage(after='configuration_end')
def evaluate_build_attrs(ctx, cfg, attrs, build_spec):
    add_attrs = evaluate_dict_with_conditions(ctx.stack_spec['build'], cfg)
    for key, value in add_attrs.items():
        if isinstance(value, basestring):
            add_attrs[key] = substitute(value, cfg)
    attrs.update(add_attrs)

def build_yaml_profile(config, logger, spec_dir, profile_name, cfg):

    stack_spec = parse_stack_spec(spec_dir)

    ctx = StackBuildContext(pipeline,
                            logger=logger,
                            build_store=BuildStore.create_from_config(config, logger),
                            source_cache=SourceCache.create_from_config(config, logger),
                            cache=DiskCache.create_from_config(config, logger),
                            stack_spec=stack_spec)
    
    profile_doc = evaluate_dict_with_conditions(stack_spec['profiles'][profile_name], cfg)
    for package, query in profile_doc.items():
        if query is None:
            query = {}
        if 'package' not in query:
            query['package'] = package

        package_cfg = dict(cfg)
        package_cfg.update(query)
        package_cfg = normalize_cfg_vars(package_cfg)

        package_attrs = {}
        package_build_spec = {
            "build": {
                "script": [],
                "import": [],
                "env": {},
                "env_nohash": {}},
            "files": [],
            "sources": [],
            "name": package_cfg['package'],
            "version": 'n' # for now
            }
                
        pipeline.run_pipeline(ctx, package_cfg, package_attrs, package_build_spec)
        pprint( package_build_spec)

    #pprint( doc['build'])
    #pprint(profile_doc)
