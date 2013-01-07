import subprocess
import errno

from ..core.cache import NullCache

def get_host_packages(cache=NullCache()):
    """Returns a HostPackages object corresponding to the current host
    """
    try:
        proc = subprocess.Popen(['dpkg-query', '--version'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except OSError, e:
        if e.errno != errno.ENOENT:
            raise
    else:
        proc.communicate()
        proc.wait()
        from .debian import DebianHostPackages
        return DebianHostPackages()

    raise NotImplementedError('No HostPackages support for this system')
    
