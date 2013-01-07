from .utils import temp_working_dir
from ...deps.distlib.glob import iglob as ant_iglob

# We used to have our own ant_glob; this testcase is left in place but really
# tests distlib's glob

import os
from os.path import join as pjoin
from os import makedirs

def makefiles(lst):
    for x in lst:
        x = x.strip()
        dirname, basename = os.path.split(x)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with file(x, 'w') as f:
            pass

def glob_files(p):
    return [x for x in ant_iglob(p) if os.path.isfile(x)]

def test_basic():
    with temp_working_dir() as d:
        makefiles('a0/b0/c0/d0.txt a0/b0/c0/d1.txt a0/b1/c1/d0.txt a0/b.txt a0/b.txt2'.split())

        def check(expected, pattern):
            # check relative
            assert sorted(expected) == sorted(glob_files(pattern))
            # check absolute
            abs_expected = [os.path.realpath(e) for e in expected]
            with temp_working_dir() as not_d:
                assert sorted(abs_expected) == sorted(glob_files(pjoin(d, pattern)))
        
        yield (check, ['a0/b0/c0/d0.txt'],
               'a0/b0/c0/d0.txt')
        yield (check, ['a0/b1/c1/d0.txt', 'a0/b0/c0/d0.txt'],
              'a0/**/d0.txt')
        yield (check, ['a0/b.txt', 'a0/b1/c1/d0.txt', 'a0/b0/c0/d0.txt', 'a0/b0/c0/d1.txt'],
              'a0/**/*.txt')
        yield (check, ['a0/b0/c0/d0.txt', 'a0/b0/c0/d1.txt'],
              '**/b0/**/*.txt')
