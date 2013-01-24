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

hdistjail = hs.Package(
    package='hdistjail',
    version='0.1.dev',
    recipe='pure-make',
    git_repos=['git@github.com:hashdist/hdist-jail.git gen'],
    sources=['git:e367142ea795ac0a197efb3edf60cf6b3b3d4486'],
    build_deps=[unix, gcc]
    )

zlib = hs.Package(
    package='zlib',
    version='1.2.7',
    recipe='configure-make-install',
    downloads=['http://downloads.sourceforge.net/project/libpng/zlib/1.2.7/zlib-1.2.7.tar.gz'],
    sources=['tar.gz:7kojzbry564mxdxv4toviu7ekv2r4hct'],
    build_deps=[unix, gcc],
    configure=['--prefix=${ARTIFACT}', '--enable-shared'])

hdf5 = hs.Package(
    package='hdf5',
    version='1.8.10',
    recipe='configure-make-install',
    downloads=['http://www.hdfgroup.org/ftp/HDF5/current/src/hdf5-1.8.10.tar.bz2'],
    sources=['tar.bz2:7jxgwn5xs5xnvsdaomvypridodr35or2'],
    configure=['--prefix=${ARTIFACT}', '--with-szlib', '--with-pic'],
    jail='warn',
    build_deps=[zlib, unix, gcc, hdistjail])

profile = hs.Package(
    package='profile',
    version='n',
    recipe='profile',
    soft_deps=[hdf5])
    

def get_profile_spec(config, logger, profile_name):
    if profile_name != 'default':
        raise hs.IllegalStackSpecError()
    return profile

#def get_pipeline(config, logger):
#    return 

#pipeline = hs.create_default_pipeline()

#from hashdist.hdist_logging import Logger, DEBUG
#from hashdist.core import load_configuration_from_inifile
#ogger = Logger(DEBUG)
#config = load_configuration_from_inifile('/home/dagss/.hdist')

#results = hs.build_packages(config, logger, pipeline, [profile])
#pprint(results)





## szip = hr.ConfigureMakeInstall(
## szip = hr.ConfigureMakeInstall('szip', '2.1',
##                                'git://github.com/erdc-cm/szip.git',
##                                'git:87863577a4656d5414b0d598c91fed1dd227f74a',
##                                configure_flags=['--with-pic'],
##                                unix=unix, gcc=gcc)

#profile = hr.Profile([zlib])

#hr.cli.stack_script_cli(profile)


