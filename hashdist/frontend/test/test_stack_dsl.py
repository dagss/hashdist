from ...deps import yaml

from nose.tools import eq_, ok_, assert_raises
from nose import SkipTest
from pprint import pprint
from textwrap import dedent

from ...core.test.utils import temp_dir

from ..marked_yaml import marked_yaml_load
from ..stack_dsl import *



def cat(filename, contents):
    with open(filename, 'w') as f:
        f.write(dedent(contents))

def test_partial_satisfy():
    expr = Match('foo', 1) & Match('bar', 1) & Match('baz', 2)
    eq_(expr, expr.partial_satisfy(dict(foo=2)))
    eq_(Match('bar', 1), expr.partial_satisfy(dict(foo=1, baz=2)))
    eq_(Match('bar', 1) & Match('baz', 2),
        expr.partial_satisfy(dict(foo=1)))
    eq_(TrueCondition(), expr.partial_satisfy(dict(foo=1, bar=1, baz=2)))
    eq_(TrueCondition(), TrueCondition().partial_satisfy({}))

def test_merge_parsed_dicts():
    # basic non-conditional case
    t = merge_parsed_dicts({'a': {'b': Select((TrueCondition(), 3))},
                            'x': Select((TrueCondition(), 1))},
                           {'a': {'c': Select((TrueCondition(), 4)),
                                  'd': Select((TrueCondition(), 5))}})
    eq_({'a': {'b': Select((TrueCondition(), 3)),
               'c': Select((TrueCondition(), 4)),
               'd': Select((TrueCondition(), 5))},
         'x': Select((TrueCondition(), 1))},
         t)
    # merge conditions
    t = merge_parsed_dicts({'a': {'b': Select((Match('package', 'bar'), 3))},
                            'x': Select((TrueCondition(), 1))},
                           {'a': {'b': Select((Match('package', 'foo'), 4)),
                                  'd': Select((TrueCondition(), 5))}})
    eq_({'a': {'b': Select((Match('package', 'bar'), 3),
                           (Match('package', 'foo'), 4)),
               'd': Select((TrueCondition(), 5))},
         'x': Select((TrueCondition(), 1))},
        t)

def test_parse_dict_with_conditions():
    doc = yaml.safe_load('''
    package=foo:
        version=bar:
            a: 1
            nested: {a: 2, b: 3}
        b: 2
    a: 3
    c: 4
    ''')
    t = parse_dict_with_conditions(doc)
    eq_({'a': Select((TrueCondition(), 3),
                      (Match('package', 'foo') & Match('version', 'bar'), 1)),
         'b': Select((Match('package', 'foo'), 2)),
         'c': Select((TrueCondition(), 4)),
         'nested': {'a': Select((Match('package', 'foo') & Match('version', 'bar'), 2)),
                    'b': Select((Match('package', 'foo') & Match('version', 'bar'), 3))}},
        t)

def test_evaluate_empty_dict():
    doc = marked_yaml_load('''
    foo: {}
    ''')
    t = evaluate_dict_with_conditions(doc, {})
    assert dict(foo={}) == t

def test_evaluate_dict_with_conditions():
    # simplest case
    rules = parse_dict_with_conditions(yaml.safe_load('''
    package=foo:
        version=1.1:
            a: 1
            nested: {a: 2, b: 3}
        b: 2
        frob=borf:
            nested:
                a: 3
    z: 4
    '''))

    eq_(dict(b=2, z=4, nested={}),
        evaluate_dict_with_conditions(rules, dict(package='foo')))
    eq_(dict(a=1, b=2, z=4, nested=dict(a=2, b=3)),
        evaluate_dict_with_conditions(rules, dict(package='foo', version='1.1')))
    eq_(dict(z=4, nested={}),
        evaluate_dict_with_conditions(rules, {}))

    eq_(dict(a=1), evaluate_dict_with_conditions(rules, dict(package='foo', version='1.1'), ['a']))

    with assert_raises(ConditionsNotNested):
        evaluate_dict_with_conditions(rules, dict(package='foo', version='1.1', frob='borf'))

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
    - package=bar:
      - bar
    - package=baz:
      - version=3:
        - baz
    - foo
    - package=bar:
      - bar
    '''))

    eq_(['foo'],
        evaluate_list_with_conditions(rules, {}))
    eq_(['bar', 'foo', 'bar'],
        evaluate_list_with_conditions(rules, dict(package='bar')))
    eq_(['baz', 'foo'],
        evaluate_list_with_conditions(rules, dict(package='baz', version='3')))
    eq_(['foo'],
        evaluate_list_with_conditions(rules, dict(package='baz')))
    
def test_ast_node_comparison():
    assert TrueCondition() > Match('package', 'foo')
    assert Match('package', 'foo') < TrueCondition()
    a = Select((TrueCondition(), 'root'),
               (Match('package', 'cond_include'), 'in_cond_included'))
    b = Select((Match('package', 'cond_include'), 'in_cond_included'),
               (TrueCondition(), 'root'))
    assert a == a
    assert a == b
    
def test_include():
    with temp_dir() as d:
        cat(pjoin(d, 'stack.yml'), '''\
        include:
          - foo
          - package=cond_include:
            - cond_included

        build:
          over_by_cond_include: root
          over_by_cond_in_include: root
          two_plus_two=4:
            two_plus_two_a: root
        ''')

        cat(pjoin(d, 'foo.yml'), '''\
        include:
          - bar
        build:
          by_include_foo: in_foo
        ''')

        cat(pjoin(d, 'bar.yml'), '''\
        build:
          by_include_bar: in_bar
          two_plus_two=4:
            two_plus_two_b: in_bar
        ''')
        
        cat(pjoin(d, 'cond_included.yml'), '''\
        build:
          over_by_cond_in_include: in_cond_included
        profile:
          default:
            another_section: yup
        ''')

        t = parse_stack_dsl_file(d)
        #pprint(t)
        eq_({'build': {'by_include_bar': Select((TrueCondition(), 'in_bar')),
                       'by_include_foo': Select((TrueCondition(), 'in_foo')),
                       'over_by_cond_in_include': Select((TrueCondition(), 'root'),
                                                         (Match('package', 'cond_include'), 'in_cond_included')),
                       'over_by_cond_include': Select((TrueCondition(), 'root')),
                       'two_plus_two_a': Select((Match('two_plus_two', '4'), 'root')),
                       'two_plus_two_b': Select((Match('two_plus_two', '4'), 'in_bar'))},
             'profile': {'default': {'another_section': Select((Match('package', 'cond_include'), 'yup'))}}},
            t)


