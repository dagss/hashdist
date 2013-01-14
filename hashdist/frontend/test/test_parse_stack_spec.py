from ...deps import yaml

from nose.tools import eq_, ok_, assert_raises
from .. import parse_stack_spec
from ..parse_stack_spec import *
from pprint import pprint
    
def test_parse_rules_doc():
    doc = yaml.safe_load('''
    project=foo:
        version=1.1:
            a: 1
        b: 2
    a: 3
    z: 4
    ''')
    t = parse_rules_doc(doc)#, dict(project='foo', version='1.1'))
    eq_([Assign('a', 3),
        (Match('project', 'foo'),
         [(Match('version', '1.1'), [Assign('a', 1)]),
          Assign('b', 2)]),
         Assign('z', 4)],
        t)

def test_evaluate_rules():
    rules = parse_rules_doc(yaml.safe_load('''
    project=foo:
        version=1.1:
            a: 1
        b: 2
    z: 4
    '''))

    assert dict(b=2, z=4) == evaluate_rules(rules, dict(project='foo'))
    assert dict(a=1, b=2, z=4) == evaluate_rules(rules, dict(project='foo', version='1.1'))
    assert dict(z=4) == evaluate_rules(rules, {})

    # conflicting settings
    rules = parse_rules_doc(yaml.safe_load('''
    a: 1
    project=foo:
        a: 1
    '''))
    try:
        evaluate_rules(rules, {})
    except IllegalStackSpecError:
        assert False
    with assert_raises(IllegalStackSpecError):
        evaluate_rules(rules, dict(project='foo'))
    
    
