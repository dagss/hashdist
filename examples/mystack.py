import hashdist.stack_api as hs
from pprint import pprint

unix = hs.Package(
    package='unix',
    version='n',
    recipe='nonhashed-host-symlinks',
    programs=[
        {'prefix': '/',
         'select': (
             "cat cp chmod chown cpio date dd df echo egrep false"
             " fgrep grep hostname ln ls mkdir mv open"
             " ps  pwd readlink rm rmdir sed sleep sync tar touch true uname which"
             # ...and with some doubt:
             " bash").split()
         },
        {'prefix': '/usr',
         'select': (
             # coreutils
             "expr printf csplit who stdbuf"
             " timeout comm [ head sha224sum tr sha256sum pathchk nice"
             " fmt chcon hostid base64 paste sort tee uniq sum stat fold arch install"
             " logname nproc wc sha1sum users sha384sum join pr printenv unexpand"
             " split tsort cut link cksum whoami env yes mkfifo id factor"
             " expand basename nl tty shuf groups tac ptx truncate tail test"
             " unlink sha512sum du dirname od md5sum seq"
             # awk
             " awk gawk pgawk igawk"
             # findutils
             " find xargs"
             # diffutils
             " sdiff cmp diff3 diff"
             # make
             " make").split()}
        ])

gcc = hs.Package(
    package='gcc',
    version='n',
    recipe='nonhashed-host-symlinks',
    programs=[
        {'prefix': '/usr',
         'select': (
             "addr2line ar strings readelf size gprof objcopy ld.gold c++filt ld.bfd as objdump"
             "nm elfedit strip ranlib ld gold gcc g++ cc"
             ).split()
         }
        ])


zlib = hs.Package(
    package='zlib',
    version='1.2.7',
    recipe='configure-make-install',
    downloads=['http://downloads.sourceforge.net/project/libpng/zlib/1.2.7/zlib-1.2.7.tar.gz'],
    sources=['tar.gz:7kojzbry564mxdxv4toviu7ekv2r4hct'],
    build_deps=[unix, gcc],
    configure=['--prefix=${ARTIFACT}', '--enable-shared'])

profile = hs.Package(
    package='profile',
    version='n',
    recipe='profile',
    soft_deps=[zlib])
    


pipeline = hs.create_default_pipeline()

from hashdist.hdist_logging import Logger, DEBUG
from hashdist.core import load_configuration_from_inifile
logger = Logger(DEBUG)
config = load_configuration_from_inifile('/home/dagss/.hdist')

results = hs.build_packages(config, logger, pipeline, [profile])
pprint(results)





## szip = hr.ConfigureMakeInstall(
## szip = hr.ConfigureMakeInstall('szip', '2.1',
##                                'git://github.com/erdc-cm/szip.git',
##                                'git:87863577a4656d5414b0d598c91fed1dd227f74a',
##                                configure_flags=['--with-pic'],
##                                unix=unix, gcc=gcc)
## hdf5 = hr.ConfigureMakeInstall('hdf5', '1.8.10',
##                                'http://www.hdfgroup.org/ftp/HDF5/current/src/hdf5-1.8.10.tar.bz2',
##                                'tar.bz2:7jxgwn5xs5xnvsdaomvypridodr35or2',
##                                configure_flags=['--with-szlib', '--with-pic'],
##                                zlib=zlib, szip=szip, unix=unix, gcc=gcc)

#profile = hr.Profile([zlib])

#hr.cli.stack_script_cli(profile)


