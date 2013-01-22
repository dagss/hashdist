from .recipes import Recipe

class Profile(Recipe):
    def __init__(self, dependency_lst):
        if any([dep.is_virtual for dep in dependency_lst]):
            raise ValueError("should not put virtual artifacts in a profile")
        dependencies = dict((dep.package, dep) for dep in dependency_lst)
        Recipe.__init__(self,
                        package="profile",
                        version="n",
                        build_deps=dependencies)

    def get_commands(self):
        return [["hdist", "create-profile", "--key=parameters/profile", "build.json", "$ARTIFACT"]]

    def get_dependencies_spec(self):
        # we don't need the dependencies in the profile build environment...
        return []

    def get_parameters(self):
        profile = []
        for ref, dep in self.build_deps.iteritems():
            before = [bef.get_artifact_id() for bef in dep.build_deps.values()
                      if bef.in_profile]
            profile.append({"id": dep.get_artifact_id(), "before": before})
        return {"profile": profile}
