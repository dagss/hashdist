import re
from nose import SkipTest
from nose.tools import eq_

from .. import glob
from ..glob import StringTerm, single_star, double_star, BraceTerm

def test_regexes():
    def check(expected_abs, expected_expr, input):
        got_abs, got_expr = glob.parse_glob(input)
        eq_(expected_abs, got_abs)
        eq_(expected_expr, got_expr)

    yield (check, False,
           [[StringTerm('foo')]],
           'foo')
    yield (check, False,
           [[StringTerm('foo')], [StringTerm('bar')]],
           'foo/bar')
    yield (check, True,
           [[StringTerm("foo")], [StringTerm("bar")]],
           '/foo/bar')
    yield (check, False,
           [[StringTerm("foo")], [single_star, StringTerm("bar")], [single_star, StringTerm(".a")], [double_star]],
           'foo/*bar/*.a/**')
    yield (check, False,
           [[StringTerm("foo"), BraceTerm(['1', '2', 'a/c'])], [StringTerm("bar")]],
           'foo{1,2,a/c}/bar')
