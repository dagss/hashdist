"""
:mod:`hashdist.core.build_store` --- Build artifact store
=========================================================

Principles
----------

The build store is the very core of Hashdist: Producing build artifacts
identified by hash-IDs. It's important to have a clear picture of just
what the build store is responsible for and not.

Nix takes a pure approach where an artifact hash is guaranteed to
identify the resulting binaries (up to anything inherently random in
the build process, like garbage left by compilers). In contrast,
Hashdist takes a much more lenient approach where the strictness is
configurable. The primary goal of Hashdist is to make life simpler
by reliably triggering rebuilds when software components are updated,
not total control of the environment (in which case Nix is likely
the better option).

The *only* concern of the build store is managing the result of a
build.  So the declared dependencies in the build-spec are not the
same as "package dependencies" found in higher-level distributions;
for instance, if a pure Python package has a NumPy dependency, this
should not be declared in the build-spec because NumPy is not needed
during the build; indeed, the installation can happen in
parallel. Assembing artifacts together in a usable run-time system is
the job of :mod:`hashdist.core.profile`.


Artifact IDs
------------

A Hashdist artifact ID has the form ``name/version/hash``, e.g.,
``zlib/1.2.7/fXHu+8dcqmREfXaz+ixMkh2LQbvIKlHf+rtl5HEfgmU``.

 * `name` is a descriptive name for the package
 * `version` describes the specific build in human-friendly terms;
   this may be a simple version number (``1.2``) or something
   more descriptive (``1.2-beta-intel-openblas-avx``). For simplicity
   we require this to always be present; by convention set it to ``n`` for
   "does not apply" or ``dev`` for "not released yet".
 * `hash` is a secure sha-256 hash of the build specification (43 characters)

All explicit references to build artifacts happens by using the full
three-part ID.

For the artifact paths on disk, a shortened form (4-char hash) is used
to make things more friendly to the human user. If there is a
collision, the length is simply increased for the one that comes
later. Thus, the example above could be stored on disk as
``~/.hdist/opt/zlib/1.2.7/fXHu``, or ``~/.hdist/opt/zlib/1.2.7/fXHu+``
in the (rather unlikely) case of a collision. There is a symlink
from the full ID to the shortened form. See also Discussion below.

Build specifications and inferring artifact IDs
-----------------------------------------------

The fundamental object of the build store is the JSON build
specification.  If you know the build spec, you know the artifact ID,
since the former is the hash of the latter. The key is that both
`dependencies` and `sources` are specified in terms of their hashes.

An example build spec:

.. code-block:: python
    
    {
        "name" : "<name of piece of software>",
        "version" : "<human-readable description what makes this build special>",
        "dependencies" : [
            {"ref": "bash", "id": "virtual:bash"},
            {"ref": "make", "id": "virtual:gnu-make/3+"},
            {"ref": "gcc", "id": "zlib/1.2.7/fXHu+8dcqmREfXaz+ixMkh2LQbvIKlHf+rtl5HEfgmU"},
            {"ref": "unix", "id": "virtual:unix"},
            {"ref": "zlib", "id": "gcc/host-4.6.3/q0VSL7JmzH1P17meqITYc4kMbnIjIexrWPdlAlqPn3s"},
         ],
         "sources" : [
             {"key": "git:c5ccca92c5f136833ad85614feb2aa4f5bd8b7c3"},
             {"key": "tar.bz2:RB1JbykVljxdvL07mN60y9V9BVCruWRky2FpK2QCCow", "target": "sources", "strip": 1},
             {"key": "files:5fcANXHsmjPpukSffBZF913JEnMwzcCoysn-RZEX7cM"}
         ],
         "files" : [
             { "target": "build.sh",
               "contents": [
                 "set -e",
                 "./configure --prefix=\\"${TARGET}\\"",
                 "make",
                 "make install"
               ]
             }
         ],
         "commands" : [["bash", "build.sh"]],
    }

The build environment
---------------------

The build environment is totally clean except for what is documented here.
``$PATH`` is reset as discussed in the next section.

The build starts in a temporary directory ``$BUILD`` with *sources*
and *files* unpacked into it, and should result in something being
copied/installed to ``$TARGET``. The build specification is available
under ``$BUILD/build.json``, and output redirected to
``$BUILD/build.log``; these two files will also be present in
``$TARGET`` after the build.


Build specification fields
--------------------------

**name**:
    See previous section

**version**:
    See previous section

**dependencies**:
    The dependencies needed for the *build* (after the
    artifact is built these have no effect).

    * **ref**: A name to use to inject information of this dependency
      into the build environment. Above, 
      ``$zlib`` will be the absolute path to the ``zlib`` artifact,
      ``$zlib_id`` will be the full artifact ID, while
      ``$zlib_relpath`` will be the relative path from ``$PREFIX`` to the
      zlib artifact.

    * **id**: The artifact ID. If the value is prepended with
      ``"virtual:"``, the ID is a virtual ID, used so that the real
      one does not contribute to the hash. See section on virtual
      dependencies below.

    Each dependency that has a ``bin`` sub-directory will have this inserted
    in ``$PATH`` in the order the dependencies are listed (and these
    are the *only* entries in ``$PATH``, ``/bin`` etc. are not present).

    **Note**: The order affects the hash (since it affects ``$PATH``).
    Whenever ordering does not matter, the list should be sorted prior
    to input by the ``ref`` argument to maintain hash stability.

**sources**:
    Unpacked into the temporary build directory. The optional ``target`` parameter
    gives a directory they should be extracted to (default: ``"."``). The ``strip``
    parameter (only applies to tarballs) acts like the
    `tar` ``--strip-components`` flag.

    Order does not affect the hashing. The build will fail if any of
    the archives contain conflicting files.

**files**:
    Embed small text files in-line in the build spec. This is really equivalent
    to uploading the file to the source store, but can provide more immediate
    documentation. **target** gives the target filename and **contents** is
    a list of lines (which will be joined by the platform newline character).

    For anything more than a hundred lines or so (small scripts and configuration
    files), you should upload to the source cache and put a ``files:...`` key
    in *sources* instead.

    Order does not affect hashing.

**commands**:
    Executed to perform the build.

    Note that while more than one command is allowed, and they will be
    executed in order, this is not a shell script: Each command is
    spawned from the builder process with a pristine environment. For anything
    that is not completely trivial one should use a scripting language.


Virtual dependencies
--------------------

Some times one do not wish some dependencies to become part of the
hash.  For instance, if the ``cp`` tool is used during the build, one
is normally ready to trust that the build wouldn't have been different
if a newer version of the ``cp`` tool was used instead.

Virtual dependencies, such as ``virtual:unix`` in the example above,
are present in order. If a bug in ``cp`` is indeed discovered,

Embedding version information in the virtual artifact names provide
the possibility of recovering from mis-builds caused by bugs in the
tools provided. If a serious bug is indeed discovered in ``cp``, one
can start to use the name ``virtual:unix/r2`` instead, thus triggering
rebuilds of artifacts built with the old version.

This feature should not be over-used. For instance, GCC should almost
certainly not be a virtual dependency.

.. note::
   One should think about virtual dependencies merely as a tool that gives
   the user control (and responsibility) over when the hash should change.
   They are *not* the primary mechanism for providing software
   from the host; though software from the host will sometimes be
   specified as virtual dependencies.


Discussion
----------

Safety of the shortened IDs
'''''''''''''''''''''''''''

Hashdist will never use these to resolve build artifacts, so collision
problems come in two forms:

First, automatically finding the list of run-time dependencies from
the build dependencies. In this case one scans the artifact directory
only for the build dependencies (less than hundred). It then makes
sense to consider the chance of finding one exact string
``aaa/0.0/ZXa3`` in a random stream of 8-bit bytes, which helps
collision strength a lot, with chance "per byte" of
collision on the order :math:`2^{-(8 \cdot 12)}=2^{-96}`
for this minimal example.

If this is deemed a problem (the above is too optimistice), one can
also scan for "duplicates" (other artifacts where longer hashes
were chosen, since we know these).

The other problem can be future support for binary distribution of
build artifacts, where you get pre-built artifacts which have links to
other artifacts embedded, and artifacts from multiple sources may
collide. In this case it makes sense to increase the hash lengths a
bit since the birthday effect comes into play and since one only has 6
bits per byte. However, the downloaded builds presumably will contain
the full IDs, and so on can check if there is a conflict and give an
explicit error.

Reference
---------

"""

import os
from os.path import join as pjoin
import tempfile
import json
import shutil
import subprocess
import sys
import re
import errno

from .hasher import Hasher


class BuildFailedError(Exception):
    def __init__(self, msg, build_dir):
        Exception.__init__(self, msg)
        self.build_dir = build_dir

class InvalidBuildSpecError(ValueError):
    pass

BUILD_ID_LEN = 4
ARTIFACT_ID_LEN = 4



class BuildStore(object):

    def __init__(self, temp_build_dir, artifact_store_dir, logger,
                 keep_build_policy='never'):
        if not os.path.isdir(artifact_store_dir):
            raise ValueError('"%s" is not an existing directory' % artifact_store_dir)
        if keep_build_policy not in ('never', 'error', 'always'):
            raise ValueError("invalid keep_build_dir_policy")
        self.artifact_store_dir = os.path.realpath(artifact_store_dir)
        self.temp_build_dir = os.path.realpath(temp_build_dir)
        self.logger = logger
        self.keep_build_policy = keep_build_policy

    def delete_all(self):
        for x in [self.artifact_store_dir, self.temp_build_dir]:
            shutil.rmtree(x)
            os.mkdir(x)

    @staticmethod
    def create_from_config(config, logger):
        """Creates a SourceCache from the settings in the configuration
        """
        return BuildStore(config.get_path('builder', 'builds-path'),
                          config.get_path('builder', 'artifacts-path'),
                          logger)

    def resolve(self, artifact_id):
        """Given an artifact_id, resolve the short path for it, or return
        None if the artifact isn't built.
        """
        adir = pjoin(self.artifact_store_dir, artifact_id)
        return os.path.realpath(adir) if os.path.exists(adir) else None

    def is_present(self, build_spec):
        return self.resolve(get_artifact_id(build_spec)) is not None

    def ensure_present(self, build_spec, source_cache):
        artifact_id = get_artifact_id(build_spec)
        artifact_dir = self.resolve(artifact_id)
        if artifact_dir is None:
            build = ArtifactBuild(self, build_spec, artifact_id)
            artifact_dir = build.build(source_cache)
        return artifact_id, artifact_dir


class ArtifactBuild(object):
    def __init__(self, builder, build_spec, artifact_id):
        self.builder = builder
        self.logger = builder.logger
        self.build_spec = build_spec
        self.artifact_id = artifact_id

    def get_dependencies_env(self, relative_from):
        # Build the environment variables due to dependencies, and complain if
        # any dependency is not built
        env = {}
        for dep_name, dep_artifact in self.build_spec.get('dependencies', {}).iteritems():
            dep_dir = self.builder.resolve(dep_artifact)
            if dep_dir is None:
                raise InvalidBuildSpecError('Dependency {"%s" : "%s"} not already built, please build it first' %
                                            (dep_name, dep_artifact))
            env[dep_name] = dep_artifact
            env['%s_abspath' % dep_name] = dep_dir
            env['%s_relpath' % dep_name] = os.path.relpath(dep_dir, relative_from)
        return env

    def build(self, source_cache):
        artifact_dir, artifact_link = self.make_artifact_dir()
        try:
            self.build_to(artifact_dir, source_cache)
        except:
            shutil.rmtree(artifact_dir)
            os.unlink(artifact_link)
            raise
        return artifact_dir

    def build_to(self, artifact_dir, source_cache):
        env = self.get_dependencies_env(artifact_dir)
        keep_build_policy = self.builder.keep_build_policy

        # Always clean up when these fail regardless of keep_build_policy
        build_dir = self.make_build_dir()
        try:
            self.serialize_build_spec(artifact_dir, build_dir)
            self.unpack_sources(build_dir, source_cache)
        except:
            self.remove_build_dir(build_dir)
            raise

        # Conditionally clean up when this fails
        try:
            self.run_build_command(build_dir, artifact_dir, env)
        except subprocess.CalledProcessError, e:
            if keep_build_policy == 'never':
                self.remove_build_dir(build_dir)
                raise BuildFailedError('Build command failed with code %d' % e.returncode, None)
            else:
                raise BuildFailedError('Build command failed with code %d, result in %s' %
                                       (e.returncode, build_dir), build_dir)
        # Success
        if keep_build_policy != 'always':
            self.remove_build_dir(build_dir)
        return artifact_dir

    def make_build_dir(self):
        short_id = shorten_artifact_id(self.artifact_id, BUILD_ID_LEN)
        build_dir = orig_build_dir = pjoin(self.builder.temp_build_dir, short_id)
        i = 0
        # Try to make build_dir, if not then increment a -%d suffix until we
        # fine a free slot
        while True:
            try:
                os.makedirs(build_dir)
            except OSError, e:
                if e != errno.EEXIST:
                    raise
            else:
                break
            i += 1
            build_dir = '%s-%d' % (orig_build_dir, i)
        return build_dir

    def remove_build_dir(self, build_dir):
        rmtree_up_to(build_dir, self.builder.temp_build_dir)

    def make_artifact_dir(self):
        # try to make shortened dir and symlink to it; incrementally
        # lengthen the name in the case of hash collision
        store = self.builder.artifact_store_dir
        extra = 0
        while True:
            short_id = shorten_artifact_id(self.artifact_id, ARTIFACT_ID_LEN + extra)
            artifact_dir = pjoin(store, short_id)
            try:
                os.makedirs(artifact_dir)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
                if os.path.exists(pjoin(store, self.artifact_id)):
                    raise NotImplementedError('race condition or unclean store')
            else:
                break
            extra += 1

        # Make a symlink from the full id to the shortened one
        artifact_link = pjoin(store, self.artifact_id)
        os.symlink(os.path.split(short_id)[-1], artifact_link)
        return artifact_dir, artifact_link
 
    def serialize_build_spec(self, build_dir, artifact_dir):
        for d in [build_dir, artifact_dir]:
            with file(pjoin(d, 'build.json'), 'w') as f:
                json.dump(self.build_spec, f, separators=(', ', ' : '), indent=4, sort_keys=True)

    def unpack_sources(self, build_dir, source_cache):
        for source_item in self.build_spec['sources']:
            key = source_item['key']
            target = source_item.get('target', '.')
            full_target = os.path.abspath(pjoin(build_dir, target))
            if not full_target.startswith(build_dir):
                raise InvalidBuildSpecError('source target attempted to escape '
                                            'from build directory')
            # if an exception is raised the directory is removed, so unsafe_mode
            # should be ok
            source_cache.unpack(key, full_target, unsafe_mode=True)

    def run_build_command(self, build_dir, artifact_dir, env):
        # todo: $-interpolation in command
        command_lst = self.build_spec['command']

        env['PATH'] = os.environ['PATH'] # for now
        env['PREFIX'] = artifact_dir

        log_filename = pjoin(build_dir, 'build.log')
        self.logger.info('Building artifact %s..., follow log with' %
                         shorten_artifact_id(self.artifact_id, ARTIFACT_ID_LEN + 2))
        self.logger.info('')
        self.logger.info('    tail -f %s\n\n' % log_filename)
        with file(log_filename, 'w') as log_file:
            logfileno = log_file.fileno()
            subprocess.check_call(command_lst, cwd=build_dir, env=env,
                                  stdin=None, stdout=logfileno, stderr=logfileno)
        # On success, copy log file to artifact_dir
        shutil.copy(log_filename, pjoin(artifact_dir, 'build.log'))






def canonicalize_build_spec(spec):
    """Puts the build spec on a canonical form + basic validation

    See module documentation for information on the build specification.

    Parameters
    ----------
    spec : json-like
        The build specification

    Returns
    -------
    canonical_spec : json-like
        Canonicalized and verified build spec
    """
    def canonicalize_source_item(item):
        item = dict(item) # copy
        if 'strip' not in item:
            item['strip'] = 0
        if 'target' not in item:
            item['target'] = "."
        return item

    result = dict(spec) # shallow copy
    assert_safe_name(result['name'])
    assert_safe_name(result['version'])

    if 'sources' in result:
        sources = [canonicalize_source_item(item) for item in result['sources']]
        sources.sort(key=lambda item: item['key'])
        result['sources'] = sources

    if 'files' in result:
        result['files'] = sorted(result['files'], key=lambda item: item['target'])

    return result


_SAFE_NAME_RE = re.compile(r'[a-zA-Z0-9-_+]+')
def assert_safe_name(x):
    """Raises a ValueError if x does not match ``[a-zA-Z0-9-_+]+``.

    Returns `x`
    """
    if not _SAFE_NAME_RE.match(x):
        raise ValueError('"%s" is empty or contains illegal characters')
    return x

def get_artifact_id(build_spec):
    """Produces the hash/"artifact id" from the given build spec.

    This can be produced merely from the textual form of the spec without
    considering any run-time state on any system.
    
    """
    digest = Hasher(build_spec).format_digest()
    name = assert_safe_name(build_spec['name'])
    version = assert_safe_name(build_spec['version'])
    
    return '%s/%s/%s' % (name, version, digest)

def shorten_artifact_id(artifact_id, length):
    """Shortens the hash part of the artifact_id to the desired length
    """
    return artifact_id[:artifact_id.rindex('/') + length + 1]

def rmtree_up_to(path, parent):
    """Executes shutil.rmtree(path), and then removes any empty parent directories
    up until (and excluding) parent.
    """
    path = os.path.realpath(path)
    parent = os.path.realpath(parent)
    if path == parent:
        return
    if not path.startswith(parent):
        raise ValueError('must have path.startswith(parent)')
    shutil.rmtree(path)
    while path != parent:
        path, child = os.path.split(path)
        if path == parent:
            break
        try:
            os.rmdir(path)
        except OSError, e:
            if e.errno != errno.ENOTEMPTY:
                raise
            break