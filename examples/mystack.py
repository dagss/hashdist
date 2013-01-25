import hashdist.recipes as hr

unix = hr.NonhashedUnix()
gcc = hr.NonhashedGccToolchain()


#gcc = hr.HostPackage(package='host-gcc',
#                     debian='gcc',
#                     redhat='gcc')

zlib = hr.ConfigureMakeInstall(package='zlib',
                               version='1.2.7',
                               download='http://downloads.sourceforge.net/project/libpng/zlib/1.2.7/zlib-1.2.7.tar.gz',
                               source='tar.gz:7kojzbry564mxdxv4toviu7ekv2r4hct',
                               build_deps=dict(unix=unix, gcc=gcc),
                               configure_flags=[])

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

profile = hr.Profile([zlib])

hr.cli.stack_script_cli(profile)


