from ...deps import yaml

from nose.tools import eq_, ok_, assert_raises
from .. import parse_stack_spec
from ..parse_stack_spec import *
from pprint import pprint
    
def test_parse_dict_with_rules():
    doc = yaml.safe_load('''
    project=foo:
        version=1.1:
            a: 1
        b: 2
    a: 3
    z: 4
    ''')
    t = parse_dict_with_rules(doc)
    eq_([(None, Assign('a', 3)),
        (Match('project', 'foo'),
         [(Match('version', '1.1'), [(None, Assign('a', 1))]),
          (None, Assign('b', 2))]),
         (None, Assign('z', 4))],
        t)

def test_parse_list_with_rules():
    doc = yaml.safe_load('''
    - project=foo:
        - version=1.1:
          - a: b # dict as list entry
        - version=1.2:
          - b
        - b
    - z
    - a: c
    ''')
    t = parse_list_with_rules(doc)
    eq_([(Match('project', 'foo'),
          [(Match('version', '1.1'), [(None, {'a': 'b'})]),
           (Match('version', '1.2'), [(None, 'b')]),
           (None, 'b')]),
         (None, 'z'),
         (None, {'a': 'c'})],
        t)



def test_evaluate_rules_dict():
    rules = parse_dict_with_rules(yaml.safe_load('''
    project=foo:
        version=1.1:
            a: 1
        b: 2
    z: 4
    '''))

    assert dict(b=2, z=4) == evaluate_dict_with_rules(rules, dict(project='foo'))
    assert dict(a=1, b=2, z=4) == evaluate_dict_with_rules(rules, dict(project='foo', version='1.1'))
    assert dict(z=4) == evaluate_dict_with_rules(rules, {})

    # conflicting settings
    rules = parse_dict_with_rules(yaml.safe_load('''
    a: 1
    project=foo:
        a: 1
    '''))
    try:
        evaluate_dict_with_rules(rules, {})
    except IllegalStackSpecError:
        assert False
    with assert_raises(IllegalStackSpecError):
        evaluate_dict_with_rules(rules, dict(project='foo'))
    
def test_evaluate_rules_list():
    rules = parse_list_with_rules(yaml.safe_load('''
    - project=bar:
      - bar
    - project=baz:
      - version=3:
        - baz
    - foo
    - project=bar:
      - bar
    '''))

    eq_(['foo'], evaluate_list_with_rules(rules, {}))
    eq_(['bar', 'foo', 'bar'], evaluate_list_with_rules(rules, dict(project='bar')))
    eq_(['baz', 'foo'],
        evaluate_list_with_rules(rules, dict(project='baz', version='3')))
    eq_(['foo'],
        evaluate_list_with_rules(rules, dict(project='baz')))
    
