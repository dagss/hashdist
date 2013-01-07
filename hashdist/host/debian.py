import re
from ..deps import sh

from ..core.cache import NullCache

from .host import WrongHostTypeError, HostPackages

_DEPENDS = re.compile(r'\s*Depends: ([^<>]+)')
_SHA1 = re.compile(r'SHA1: (.*)$')

class DebianHostPackages(HostPackages):
    def __init__(self, cache=NullCache()):
        if cache.get(DebianHostPackages, 'is_debian_system', False):
            # check already done
            return
        
        # Check that all commands are available
        try:
            sh.dpkg_query('-h')
            sh.apt_cache('-h')
        except sh.CommandNotFound, e:
            raise WrongHostTypeError('Not a Debian-based system')
    
    def is_package_installed(self, pkgname):
        try:
            out = sh.dpkg_query('-W', '-f', '${Status}', pkgname)
            installed  = (str(out) == 'install ok installed')
        except sh.ErrorReturnCode, e:
            installed = False
        return installed

    def get_immediate_dependencies(self, pkgname):
        if pkgname == 'libc6':
            # for now, break dependency cycle here; TODO: proper treatment of
            # cyclic dependencies
            return ()
            
        deps = set()
        for line in sh.apt_cache('depends', '--installed', pkgname):
            m = _DEPENDS.match(line.strip())
            if m:
                deps.add(m.group(1))
        return deps

    def get_files_of(self, pkgname):
        """Returns the names of the files installed by the given package
        """
        result = []
        for line in sh.dpkg_query('--listfiles', pkgname):
            line = line.strip()
            result.append(line)
        return result

    def get_package_key(self, pkgname):
        try:
            for line in sh.apt_cache('show', pkgname):
                m = _SHA1.match(line.strip())
                if m:
                    return 'deb:' + m.group(1)
        except sh.ErrorReturnCode, e:
            raise UnknownPackageError(pkgname)

    def get_system_description(self):
        return 'Debian'
