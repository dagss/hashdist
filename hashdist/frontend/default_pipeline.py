"""
Pipeline functions that are not recipes; these are typically more
standard and take effect for most packages.
"""

from .build import Pipeline
from ..deps.yaml import safe_load as yaml

pipeline = Pipeline()

@pipeline.add_assemble_stage(after='profile_install')
def profile_install_symlink_everything(ctx, pkg, build_spec):
    if pkg['recipe'] == 'profile':
        return
    # todo: when should this not happen?
    artifact_spec_file = yaml('''
    target: $ARTIFACT/artifact.json
    object:
      install:
        script:
          - ["@hdist", create-links, --key=install/links, artifact.json]
        links:
          - action: symlink
            select: $ARTIFACT/*/**/*
            prefix: $ARTIFACT
            target: $PROFILE
    ''')

    build_spec['files'].append(artifact_spec_file)

@pipeline.add_assemble_stage(before='assemble_end')
def jail(ctx, pkg, build_spec):
    if pkg.get('jail', 'none') == 'none':
        return

    if not any(package.package == 'hdistjail' for package in pkg['build_deps']):
        raise Exception("need dependency on hdistjail to use jail") # TODO auto

    cmds = [
        ['LD_PRELOAD=$HDISTJAIL/lib/libhdistjail.so.1'],
        ['HDIST_JAIL_LOG=$(hdist', 'logpipe', 'jail', 'WARNING', ')'],
        ['HDIST_JAIL_WHITELIST=${BUILD}/whitelist'],
        ['hdist>whitelist', 'build-whitelist'],
        ]
    
    script = build_spec['build']['script']
    script[:] = cmds + script


@pipeline.add_assemble_stage(before='assemble_end')
def check_script_present(ctx, pkg, build_spec):
    if len(build_spec['build']['script']) == 0:
        raise Exception("no script present (did you set 'recipe'?)")

@pipeline.add_assemble_stage(after='assemble_start')
def specify_sources(ctx, pkg, build_spec):
    sources = pkg.get('sources', ())
    for item in sources:
        strip = 1 if item.startswith('tar') else 0
        build_spec['sources'].append(dict(strip=strip, target='.', key=item))

@pipeline.add_assemble_stage(after='check_script_present')
def write_files(ctx, pkg, build_spec):
    if build_spec['files']:
        build_spec['build']['script'].insert(0, ['@hdist', 'build-write-files'])


@pipeline.add_assemble_stage(after='check_script_present')
def unpack_sources(ctx, pkg, build_spec):
    if build_spec['sources']:
        build_spec['build']['script'].insert(0, ['@hdist', 'build-unpack-sources'])

