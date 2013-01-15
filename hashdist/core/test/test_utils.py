from nose.tools import eq_, assert_raises

from ..utils import substitute

def test_substitute():
    env = {"A": "a", "B": "b"}
    def check(want, x):
        eq_(want, substitute(x, env))
    def check_raises(x):
        with assert_raises(KeyError):
            substitute(x, env)
    yield check, "ab", "$A$B"
    yield check, "ax", "${A}x"
    yield check, "\\", "\\"
    yield check, "\\\\", "\\\\"
    yield check, "a$${x}", "${A}\$\${x}"
    yield check_raises, "$Ax"
    yield check_raises, "$$"

