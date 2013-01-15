from textwrap import dedent

from .recipes import Recipe, FetchSourceCode

import multiprocessing
ncores = multiprocessing.cpu_count()

class ConfigureMakeInstall(Recipe):

    def get_commands(self):
        return [
            ["hdist", "build-unpack-sources"],
            ["hdist", "build-write-files"],
            [
                ['LDFLAGS=$HDIST_LDFLAGS'],
                ['CFLAGS=$HDIST_CFLAGS'],
                ['./configure', '--prefix=${ARTIFACT}'] + self.configure_flags,
            ],
            ['make', '-j%d' % ncores],
            ['make', 'install']
            ]
    
    def get_files(self):
        artifact_json = {
          "install": {
              "script": [
                  ["@hdist", "create-links", "--key=links", "artifact.json"]
              ]
          },
          "links": [
            {"action": "symlink", "select": "$ARTIFACT/*/**/*", "prefix": "$ARTIFACT",
             "target": "$PROFILE"}
          ]
        }

        return [
            {"target": "$ARTIFACT/artifact.json", "object": artifact_json}
        ]
