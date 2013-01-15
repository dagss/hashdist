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

def test_parse_dict_with_conditions():
    doc = yaml.safe_load('''
    project=foo:
        version=bar:
            a: 1
        b: 2
    a: 3
    c: 4
    ''')
    t = parse_dict_with_conditions(doc)
    eq_({'a': Select((TrueCondition(), 3), (Match('project', 'foo') & Match('version', 'bar'), 1)),
         'b': Select((Match('project', 'foo'), 2)),
         'c': Select((TrueCondition(), 4))},
        t)

def test_evaluate_dict_with_conditions():
    # simplest case
    rules = parse_dict_with_conditions(yaml.safe_load('''
    package=foo:
        version=1.1:
            a: 1
        b: 2
    z: 4
    '''))

    eq_(dict(b=2, z=4),
        evaluate_dict_with_conditions(rules, dict(package='foo')))
    eq_(dict(a=1, b=2, z=4),
        evaluate_dict_with_conditions(rules, dict(package='foo', version='1.1')))
    eq_(dict(z=4),
        evaluate_dict_with_conditions(rules, {}))

    # more specific overrides
    rules = parse_dict_with_conditions(yaml.safe_load('''
    a: 1
    package=foo:
      a: 2
      version=2.0:
        a: 3
    version=1.0:
      a: 4
    '''))
    eq_(dict(a=1), evaluate_dict_with_conditions(rules, {}))
    eq_(dict(a=2), evaluate_dict_with_conditions(rules, dict(package='foo')))
    eq_(dict(a=3), evaluate_dict_with_conditions(rules, dict(package='foo', version='2.0')))
    with assert_raises(ConditionsNotNested):
        evaluate_dict_with_conditions(rules, dict(package='foo', version='1.0'))
    
def test_parse_list_with_conditions():
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
    t = parse_list_with_conditions(doc)
    eq_(t, [Extend(TrueCondition(), ['a', 'a']),
            Extend(Match('package', 'foo') & Match('version', 'bar'), ['a', 'b']),
            Extend(Match('package', 'foo'), ['b']),
            Extend(TrueCondition(), ['a', 'c'])])

def test_evaluate_list_with_conditions():
    rules = parse_list_with_conditions(yaml.safe_load('''
    - project=bar:
      - bar
    - project=baz:
      - version=3:
        - baz
    - foo
    - project=bar:
      - bar
    '''))

    eq_(['foo'],
        evaluate_list_with_conditions(rules, {}))
    eq_(['bar', 'foo', 'bar'],
        evaluate_list_with_conditions(rules, dict(project='bar')))
    eq_(['baz', 'foo'],
        evaluate_list_with_conditions(rules, dict(project='baz', version='3')))
    eq_(['foo'],
        evaluate_list_with_conditions(rules, dict(project='baz')))
    

def test_include():
    with temp_dir() as d:
        cat(pjoin(d, 'stack.yml'), '''\
        include:
          - foo
          - project=cond_include:
            - cond_included

        build:
          over_by_cond_include: root
          over_by_include_a: root
          over_by_include_b: root
          over_by_cond_in_include: root
          two_plus_two=4:
            two_plus_two_a: root
        ''')

        cat(pjoin(d, 'foo.yml'), '''\
        include:
          - bar
        build:
          over_by_include_a: in_foo
        ''')

        cat(pjoin(d, 'bar.yml'), '''\
        build:
          over_by_include_b: in_bar
          two_plus_two=4:
            two_plus_two_a: in_bar
            two_plus_two_b: in_bar
            two_plus_two_c: in_bar
        ''')
        
        cat(pjoin(d, 'cond_included.yml'), '''\
        build:
          over_by_cond_in_include: in_cond_included
        profile:
          another_section: yup
        ''')

        t = parse_stack_spec(d)
        #pprint(t)
        eq_({'build':
             {'over_by_cond_in_include': Select((TrueCondition(), 'root'),
                                                (Match('project', 'cond_include'), 'in_cond_included')),
              'over_by_cond_include': Select((TrueCondition(), 'root')),

              # the entries below are illegal as no configuration can pick a choice,
              # but it should be the the result of the parse nevertheless
              'over_by_include_a': Select((TrueCondition(), 'root'),
                                          (TrueCondition(), 'in_foo')),
              'over_by_include_b': Select((TrueCondition(), 'root'),
                                          (TrueCondition(), 'in_bar')),
              'two_plus_two_a': Select((Match('two_plus_two', '4'), 'root'),
                                       (Match('two_plus_two', '4'), 'in_bar')),
              'two_plus_two_b': Select((Match('two_plus_two', '4'), 'in_bar')),
              'two_plus_two_c': Select((Match('two_plus_two', '4'), 'in_bar'))},
             'profile':
             {'another_section': Select((Match('project', 'cond_include'), 'yup'))}
             },
            t)

