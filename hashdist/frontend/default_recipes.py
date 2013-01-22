from ..deps.yaml import safe_load as yaml

ncores = 4

def configure_make_install_recipe(ctx, attrs, build_spec):
    if attrs['recipe'] != 'configure-make-install':
        return

    configure_flags = attrs.get('configure', [])
    
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

def nonhashed_host_symlinks_recipe(ctx, attrs, build_spec):
    if attrs['recipe'] != 'nonhashed-host-symlinks':
        return
    # emit 'links' section in build spec
    build_spec['links'] = rules = []
    for rule in attrs['programs']:
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

def profile_recipe(ctx, attrs, build_spec):
    if attrs['recipe'] != 'profile':
        return

    # emit 'profile' section in build spec
    profile = []
    for dep in attrs['soft_deps']:
        before = [ctx.get_artifact_id(dep_dep) for dep_dep in dep.soft_deps]
        profile.append({"id": ctx.get_artifact_id(dep), "before": before})
    build_spec['profile'] = profile

    # emit command to create profile
    cmd = ["hdist", "create-profile", "--key=profile", "build.json", "$ARTIFACT"]
    build_spec['build']['script'].append(cmd)


def profile_install_symlink_everything(ctx, attrs, build_spec):
    if attrs['recipe'] == 'profile':
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

def check_script_present(ctx, attrs, build_spec):
    if len(build_spec['build']['script']) == 0:
        raise Exception("no script present (did you set 'recipe'?)")

def specify_sources(ctx, attrs, build_spec):
    sources = attrs.get('sources', ())
    for item in sources:
        strip = 1 if item.startswith('tar') else 0
        build_spec['sources'].append(dict(strip=strip, target='.', key=item))

def write_files(ctx, attrs, build_spec):
    if build_spec['files']:
        build_spec['build']['script'].insert(0, ['@hdist', 'build-write-files'])

def unpack_sources(ctx, attrs, build_spec):
    if build_spec['sources']:
        build_spec['build']['script'].insert(0, ['@hdist', 'build-unpack-sources'])

def register_recipes(pipeline):
    # todo: merge pipelines
    pipeline.add_recipe(configure_make_install_recipe)
    pipeline.add_recipe(nonhashed_host_symlinks_recipe)
    pipeline.add_recipe(profile_recipe)
    
    pipeline.add_assemble_stage(after='assemble_start', func=specify_sources)
    pipeline.add_assemble_stage(after='recipes_profile_install', func=profile_install_symlink_everything)
    pipeline.add_assemble_stage(before='assemble_end', func=check_script_present)
    pipeline.add_assemble_stage(after='check_script_present', func=write_files)
    pipeline.add_assemble_stage(after='check_script_present', func=unpack_sources)
