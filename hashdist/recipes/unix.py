from .recipes import Recipe

class NonhashedHostPrograms(Recipe):
    """
    Parameters
    ----------

    programs : dict
       Maps `prefix` to list of programs (by basename to be found in $prefix/bin) to symlink
    """
    def __init__(self, **attrs):
        Recipe.__init__(self, is_virtual=True, **attrs)

    def get_parameters(self):
        rules = []
        for prefix, program_lst in sorted(self.programs.items()):
            if prefix[-1] != '/':
                prefix += '/'
            rules.append({"action": "symlink",
                          "select": ['%sbin/%s' % (prefix, p) for p in sorted(program_lst)],
                          "prefix": prefix,
                          "target": "$ARTIFACT"})
        return {"links": rules}

    def get_commands(self):
        return [["hdist", "create-links", "--key=parameters/links", "build.json"]]

unix_programs_bin = (
    "cat cp chmod chown cpio date dd df echo egrep false"
    " fgrep grep hostname ln ls mkdir mv open"
    " ps  pwd readlink rm rmdir sed sleep sync tar touch true uname which"
    # ...and with some doubt:
    " bash"
    ).split()

# list mainly taken from Ubuntu coreutils; could probably be filtered a bit more
unix_programs_usr_bin = (
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
    " make"
    ).split()

class NonhashedUnix(NonhashedHostPrograms):
    def __init__(self):
        programs = {'/': unix_programs_bin, '/usr': unix_programs_usr_bin}
        NonhashedHostPrograms.__init__(self, package="unix", programs=programs)

gcc_stack_programs = (
    "addr2line ar strings readelf size gprof objcopy ld.gold c++filt ld.bfd as objdump"
    "nm elfedit strip ranlib ld gold gcc g++ cc"
    ).split()

class NonhashedGccToolchain(NonhashedHostPrograms):
    def __init__(self):
        programs = {'/usr': gcc_stack_programs}
        NonhashedHostPrograms.__init__(self, package="gcc-stack", programs=programs)

