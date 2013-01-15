from ...deps import yaml

from nose.tools import eq_, ok_, assert_raises
from nose import SkipTest
from .. import parse_stack_spec
from ..parse_stack_spec import *
from pprint import pprint
from textwrap import dedent

from ...core.test.utils import temp_dir


def cat(filename, contents):
    with open(filename, 'w') as f:
        f.write(dedent(contents))

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



def test_evaluate_dict_with_rules():
    # simplest case
    rules = parse_dict_rules(yaml.safe_load('''
    package=foo:
        version=1.1:
            a: 1
        b: 2
    z: 4
    '''))

    eq_(dict(b=2, z=4),
        evaluate_dict_with_rules(rules, dict(package='foo')))
    eq_(dict(a=1, b=2, z=4),
        evaluate_dict_with_rules(rules, dict(package='foo', version='1.1')))
    eq_(dict(z=4),
        evaluate_dict_with_rules(rules, {}))

    # more specific overrides
    rules = parse_dict_rules(yaml.safe_load('''
    a: 1
    package=foo:
      a: 2
      version=2.0:
        a: 3
    version=1.0:
      a: 4
    '''))
    eq_(dict(a=1), evaluate_dict_with_rules(rules, {}))
    eq_(dict(a=2), evaluate_dict_with_rules(rules, dict(package='foo')))
    eq_(dict(a=3), evaluate_dict_with_rules(rules, dict(package='foo', version='2.0')))
    with assert_raises(ConditionsNotNested):
        evaluate_dict_with_rules(rules, dict(package='foo', version='1.0'))
    
def test_evaluate_list_with_rules():
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
    

def test_parse_dict_rules():
    doc = yaml.safe_load('''
    project=foo:
        version=bar:
            a: 1
        b: 2
    a: 3
    c: 4
    ''')
    t = parse_dict_rules(doc)
    eq_({'a': Select((TrueCondition(), 3), (Match('project', 'foo') & Match('version', 'bar'), 1)),
         'b': Select((Match('project', 'foo'), 2)),
         'c': Select((TrueCondition(), 4))},
        t)

def test_parse_list_rules():
    doc = yaml.safe_load('''
    - a
    - a
    - package=foo:
        - version=bar:
            - a
            - b
        - b
    - a
    - c
    - a: b
      c: d
    ''')
    t = parse_list_rules(doc)
    eq_(t, [Extend(TrueCondition(), ['a', 'a']),
            Extend(Match('package', 'foo') & Match('version', 'bar'), ['a', 'b']),
            Extend(Match('package', 'foo'), ['b']),
            Extend(TrueCondition(), ['a', 'c'])])
    

def test_include():
    raise SkipTest()
    with temp_dir() as d:
        cat(pjoin(d, 'stack.yml'), '''\
        include:
          - foo
          - project=baz:
            - baz

        rules:
          a: a
          b: b
          project=baz:
            c: c
        ''')

        cat(pjoin(d, 'foo.yml'), '''\
        include:
          - bar
        rules:
          foo_a: foo_a
          c: foo_c
        ''')

        cat(pjoin(d, 'bar.yml'), '''\
        rules:
          two_plus_two=4:
            x=x
        ''')
        
        cat(pjoin(d, 'baz.yml'), '''\
        rules:
          baz_a: baz_a
          two_plus_two=4:
            y=y
        ''')

        print d
        print parse_stack_spec(d)
        
