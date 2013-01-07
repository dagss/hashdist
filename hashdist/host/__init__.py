import subprocess
import errno

from .host import WrongHostTypeError
from ..core.cache import NullCache

_host_packages_class = None

def get_host_packages(cache=NullCache()):
    """Returns a HostPackages object corresponding to the current host
    """
    global _host_packages_class
    if _host_packages_class is None:
        from .debian import DebianHostPackages
        result = None
        try:
            result = DebianHostPackages(cache)
        except WrongHostTypeError:
            pass
        except:
            raise
        
        try:
            proc = subprocess.Popen(['dpkg-query', '--version'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
        else:
            proc.communicate()
            proc.wait()
            _system_type = DebianHostPackages

    raise NotImplementedError('No HostPackages support for this system')
    
