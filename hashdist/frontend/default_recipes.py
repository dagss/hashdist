from ..deps.yaml import safe_load as yaml

ncores = 4

def configure_make_install(ctx, attrs, build_spec):
    if attrs['recipe'] != 'configure-make-install':
        return

    configure_flags = attrs.get('configure-flags', [])
    
    build_spec['build']['script'].extend([
            [
                ['LDFLAGS=$HDIST_LDFLAGS'],
                ['CFLAGS=$HDIST_CFLAGS'],
                ['./configure', '--prefix=${ARTIFACT}'] + configure_flags,
            ],
            ['make', '-j$NCORES'],
            ['make', 'install']
        ])
    build_spec['build']['env_nohash']['NCORES'] = str(ncores)


def symlink_everything(ctx, attrs, build_spec):
    # todo: when should this not happen?
    artifact_spec_file = yaml('''
    target: $ARTIFACT/artifact.json
    object:
      install:
        script:
          - ["@hdist", create-links, --key=links, artifact.json]
        links:
          - action: symlink
            select: $ARTIFACT/*/**/*
            prefix: $ARTIFACT
            target: $PROFILE
    ''')

    build_spec['files'].append(artifact_spec_file)

def specify_sources(ctx, attrs, build_spec):
    sources = attrs.get('sources', None)
    if sources:
        strip = 1 if sources.startswith('tar') else 0
        build_spec['sources'].append(dict(strip=strip, target='.', key=sources))

def write_files(ctx, attrs, build_spec):
    if build_spec['files']:
        build_spec['build']['script'].insert(0, ['@hdist', 'build-write-files'])

def unpack_sources(ctx, attrs, build_spec):
    if build_spec['sources']:
        build_spec['build']['script'].insert(0, ['@hdist', 'build-unpack-sources'])

def register_recipes(pipeline):
    pipeline.add_recipe(configure_make_install)
    pipeline.add_assemble_stage(after='assemble_start', func=specify_sources)
    pipeline.add_assemble_stage(after='recipes_profile_install', func=symlink_everything)
    pipeline.add_assemble_stage(before='assemble_end', func=write_files)
    pipeline.add_assemble_stage(before='assemble_end', func=unpack_sources)
