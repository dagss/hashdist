"""
Pipeline parts dealing with host
"""

#
# Host system
#


@pipeline
def probe_host(cache, package_name):
    domain, key = ('hashdist.frontend.default_recipes', 'HostPackage-instance')
    try:
        hostpkgs = cache.get(domain, key)
    except KeyError:
        hostpkgs = get_host_packages(logger, cache)
        cache.put(domain, key, hostpkgs, on_disk=False)
        for dep in hostpkgs.get_immediate_dependencies(self.host_pkg_name):
            recipe = _interned.get(dep, None)
            if recipe is None:
                recipe = _interned[dep] = HostPackage(dep)
                recipe.initialize(logger, cache)
            self.dependencies[dep] = recipe

        self.files_to_link = files = []
        for filename in hostpkgs.get_files_of(self.host_pkg_name):
            if (_INTERESTING_FILE_RE.match(filename) and os.path.isfile(filename)):
                files.append(filename)
