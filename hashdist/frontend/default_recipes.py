from .build import Pipeline
from pprint import pprint
from ..deps.yaml import safe_load as yaml

ncores = 1


pipeline = Pipeline()

@pipeline.add_recipe('configure-make-install')
def configure_make_install_recipe(ctx, pkg, build_spec):
    configure_flags = pkg.get('configure', [])
    
    build_spec['build']['script'].extend([
            [
                ['LDFLAGS=$HDIST_LDFLAGS'],
                ['CFLAGS=$HDIST_CFLAGS'],
                ['./configure'] + configure_flags,
            ],
            ['make', '-j$NCORES'],
            ['make', 'install']
        ])
    build_spec['build']['env_nohash']['NCORES'] = str(ncores)

@pipeline.add_recipe('nonhashed-host-symlinks')
def nonhashed_host_symlinks_recipe(ctx, pkg, build_spec):
    # emit 'links' section in build spec
    build_spec['links'] = rules = []
    for rule in pkg['programs']:
        prefix, select = rule['prefix'], rule['select']
        if prefix[-1] != '/':
            prefix += '/'
        rules.append({"action": "symlink",
                      "select": ['%sbin/%s' % (prefix, p) for p in sorted(select)],
                      "prefix": prefix,
                      "target": "$ARTIFACT"})
    # emit command to read 'links' section and act on it
    cmd = ["hdist", "create-links", "--key=links", "build.json"]
    build_spec['build']['script'].append(cmd)

@pipeline.add_recipe('profile')
def profile_recipe(ctx, pkg, build_spec):
    # emit 'profile' section in build spec
    profile = []
    for dep in pkg['soft_deps']:
        before = [ctx.get_artifact_id(dep_dep) for dep_dep in dep.soft_deps]
        profile.append({"id": ctx.get_artifact_id(dep), "before": before})
    build_spec['profile'] = profile

    # emit command to create profile
    cmd = ["hdist", "create-profile", "--key=profile", "build.json", "$ARTIFACT"]
    build_spec['build']['script'].append(cmd)

@pipeline.add_recipe('custom-script')
def custom_script_recipe(ctx, pkg, build_spec):
    build_spec['build']['script'].extend(pkg['script'])

@pipeline.add_assemble_stage(after='recipes_profile_install')
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
        ['LD_PRELOAD=$HDISTJAIL/lib/hdistjail.so'],
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

