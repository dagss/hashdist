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
        result = None

        from .debian import DebianHostPackages
        if DebianHostPackages.is_supported(cache):
            _host_packages_class = DebianHostPackages
        else:
            raise NotImplementedError('No HostPackages support for this system')
    return _host_packages_class(cache)
    
