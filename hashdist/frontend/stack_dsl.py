"""
:mod:`hashdist.frontend.stack_dsl` --- Domain-specifice language for describing a software stack
================================================================================================


Treatment of sections
---------------------

**include**:
    Conditions in here are propagated to the included sub-tree; which
    end up merging with the other sections.

**rules**:

    Treated as a set of assignments to a variable (LHS) from an
    expression (RHS).  There's a full dependency graph between these
    root-level assignments. While an RHS can be a dictionary
    While some values can be dicts, there is not a dependency graph between
    sub-parts of values/right hand sides.

::

    rules:
        var1: foo
        var1=foo:
            bar:
              a_dict: can_be_here
              var2=true:
                  but_is: treated_like_a_value
                  # dependency on "var1/a_dict" not possible here even
                  # if it is sibling
            # not legal: var1=..., as it would create cycle

**profiles**:
    Currently does not allow conditions. Conditions implicitly added
    through `include` will be ignored. This needs to be hashed out.

::

    profiles:
        name1:
            package:
                require-foo: true


"""

import re
import os
from os.path import join as pjoin
from functools import total_ordering
from .marked_yaml import marked_yaml_load

class IllegalStackSpecError(Exception):
    def __init__(self, msg='', node=None):
        Exception.__init__(self, msg)
        if not (hasattr(node, 'start_mark') and hasattr(node, 'end_mark')):
            node = None
        self.node = node
        

    def __str__(self):
        if self.node is None:
            return self.message
        else:
            mark = self.node.start_mark
            return ('%s:%d:%d: %s' % (mark.name, mark.line + 1, mark.column, self.message))

class ConditionsNotNestedError(IllegalStackSpecError):
    pass

class NoOptionFoundError(ValueError):
    pass

## Hmm, do we want to make it type-safe?
## class VariableType(object):
##     pass

## class StringType(VariableType):
##     @staticmethod
##     def parse(s):
##         return s

## class IntegerType(VariableType):
##     @staticmethod
##     def parse(s):
##         return int(s)

def evaluate_tree_with_conditions(node, cfg):
    if isinstance(node, Node):
        result = node.evaluate(cfg)
    elif isinstance(node, list):
        result = []
        for item in node:
            try:
                ev_item = evaluate_tree_with_conditions(item, cfg)
            except NoOptionFoundError:
                pass
            else:
                result.append(ev_item)
    elif isinstance(node, dict):
        result = {}
        for key, value in node.items():
            try:
                ev_value = evaluate_tree_with_conditions(value, cfg)
            except NoOptionFoundError:
                pass
            else:
                result[key] = ev_value
    else:
        raise AssertionError('invalid tree')
    return result

class Program(object):
    """
    Graph of assignments to variables and their inputs
    """

    def __init__(self):
        self.assignments = {} # { varname: (rhs, rhs_inputs) }
        #self.decls = {}

    #def add_variable(self, name, type):
    #    self.decls[name] = type

    def add_assignment(self, varname, rhs):
        if varname in self.assignments:
            raise AssertionError('%s already assigned to' % varname)
        self.assignments[varname] = (rhs, get_tree_inputs(rhs))

    def evaluate_all(self, cfg):
        cfg = dict(cfg)
        for key in self.assignments:
            self._evaluate_from(key, cfg)
        return cfg

    def _evaluate_from(self, varname, cfg):
        if varname not in cfg:
            # if there is never an assignment to a variable, and it is not present in cfg,
            # assume it is None
            x = self.assignments.get(varname, None)
            if x is not None:
                rhs, rhs_inputs = x
                for input_var in rhs_inputs:
                    self._evaluate_from(input_var, cfg)
                try:
                    value = evaluate_tree_with_conditions(rhs, cfg)
                except NoOptionFoundError:
                    cfg[varname] = None
                else:
                    cfg[varname] = value
            else:
                cfg[varname] = None

class Node(object):
    def __hash__(self):
        return hash(self.tuple)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.tuple == other.tuple

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        cls = self.tuple[0]
        return '%s(%s)' % (cls.__name__, ', '.join(repr(arg) for arg in self.tuple[1:]))

    def input_vars(self):
        return self._input_vars

# inspired by string.Template source code
_escape_re = re.compile(r'\\\$')
_subst_re = re.compile(r"""
  (?<!\\)\$(?:
    (?P<named>[_a-z][_a-z0-9]*)|
    {(?P<braced>[_a-z][_a-z0-9]*)}|
    (?P<illegal>)
    )
""", re.IGNORECASE | re.VERBOSE)
_get_re = re.compile(r'^\$([_a-z][_a-z0-9]*)$', re.IGNORECASE)

class StringSubst(Node):
    def __init__(self, pattern):
        self.tuple = (StringSubst, pattern)
        self.pattern = pattern
        _input_vars = []
        for m in _subst_re.finditer(pattern):
            named, braced, illegal = m.groups()
            if named is not None:
                _input_vars.append(named)
            if braced is not None:
                _input_vars.append(braced)
            if illegal is not None:
                raise IllegalStackSpecError("Invalid use of $ in '%s'" % pattern, pattern)
        self._input_vars = frozenset(_input_vars)

    def evaluate(self, cfg):
        def lookup(match):
            varname = match.group('named') or match.group('braced')
            return unicode(cfg[varname])
        x = _subst_re.sub(lookup, self.pattern)
        return _escape_re.sub('$', x)

_empty_set = frozenset()
class StringConstant(Node):
    def __init__(self, value):
        self.value = value
        self.tuple = (StringConstant, value)
        self._input_vars = _empty_set

    def evaluate(self, cfg):
        return self.value

class Get(Node):
    def __init__(self, varname):
        self.varname = varname
        self.tuple = (Get, varname)
        self._input_vars = frozenset([varname])

    def evaluate(self, cfg):
        return cfg[self.varname]

def parse_scalar(s):
    m = _get_re.match(s)
    if m:
        return Get(m.group(1))
    m = _subst_re.search(s)
    if m:
        return StringSubst(s)
    else:
        return StringConstant(s)


class Select(Node):
    def __init__(self, *options):
        # Always turn Select(Selection([a], [b]), [c]) to Select([a, b, c])
        def flatten(x):
            if type(x) is Select:
                return x.options
            else:
                return [x]
        self.options = options = sum([flatten(x) for x in options], [])
        # need to sort list of options by their conditions to make sure __eq__
        # works reliably
        options.sort()
        # if conditions are equal, we don't have a canonical order -- but then
        # we are guaranteed to have an error on evaluation anyway, so may
        # as well err now
        for i in range(len(options) - 1):
            if options[i][0] == options[i + 1][0]:
                raise IllegalStackSpecError("duplicate keys")
        self.tuple = (Select, options)

        _input_vars = set()
        for cond, value in self.options:
            _input_vars.update(cond.input_vars())
            if isinstance(value, Node):
                _input_vars.update(value.input_vars())
        self._input_vars = frozenset(_input_vars)

    def __add__(self, other):
        if other is None:
            return self
        elif not type(other) is Select:
            raise TypeError()
        else:
            return Select(*(self.options + other.options))

    def __radd__(self, other):
        return self.__add__(other)

    def __repr__(self):
        return 'Select(%s)' % (', '.join(repr(x) for x in self.options))

    def is_always_true(self):
        return all(tup[0] is True for tup in self.options)

    def find_option(self, cfg):
        """Which options out of multiple possible to pick?

        The rule is to a) ensure that all conditions are nested within one
        another, b) pick the most specific one.

        May raise ConditionsNotNestedError or NoOptionFoundError.
        
        Returns
        -------
        
        option: (Condition, Node)
            The selected option from `self.options`
        """
        def cond_children(cond):
            if type(cond) is And:
                return cond.children
            else:
                return [cond]

        # First filter options to get those that are satisfied by cfg only
        options = [opt for opt in self.options if opt[0].satisfied_by(cfg)]

        if len(options) == 0:
            raise NoOptionFoundError()
        elif len(options) == 1:
            return options[0]
        else:
            # TrueCondition is least specific, filter them out
            options = [opt for opt in options if type(opt[0]) is not TrueCondition]
            if len(options) == 0:
                raise ConditionsNotNestedError("only TrueCondition present, cannot discriminate")

            # sort by number of and-ed terms, then check that each and-ed term is a superset
            # of the previous one
            options.sort(key=lambda option: len(cond_children(option[0])))
            for i in range(len(options) - 1):
                child_cond = options[i][0]
                parent_cond = options[i + 1][0]
                if set(cond_children(child_cond)).difference(cond_children(parent_cond)):
                    raise ConditionsNotNestedError('%r not nested in %r' % (child_cond, parent_cond))
            # OK, they're all nested, select the last (most specific) one
            return options[-1]

    def evaluate(self, cfg):
        cond, node = self.find_option(cfg)
        if node is None:
            return None
        else:
            return node.evaluate(cfg)

@total_ordering
class Condition(Node):
    def __lt__(self, other):
        if type(self) != type(other):
            return type(self).__name__ < type(other).__name__
        else:
            return self._lt_same_type(other)
    
    def __and__(self, other):
        if type(self) is TrueCondition:
            return other
        elif type(other) is TrueCondition:
            return self
        elif not isinstance(other, Condition):
            raise TypeError()
        else:
            return And([self, other])

    def __rand__(self, other):
        return self.__and__(other)

class TrueCondition(Condition):
    def __init__(self):
        self.tuple = (TrueCondition,)

    def satisfied_by(self, cfg):
        return True

    def partial_satisfy(self, cfg):
        return self

    def _lt_same_type(self, other):
        return False

true_condition = TrueCondition()

class And(Condition):
    def __init__(self, children):
        # Always turn And(And([a], [b]), [c]) to And([a, b, c])
        def flatten(x):
            if type(x) is And:
                return x.children
            else:
                return [x]
        self.children = children = sum([flatten(x) for x in children], [])
        # Keep children sorted to make __eq__ work reliably
        children.sort()
        self.tuple = (And, children)

    def __repr__(self):
        if len(self.children) <= 1:
            return 'And(%s)' % repr(self.children)
        else:
            return ' & '.join(repr(x) for x in self.children)

    def satisfied_by(self, cfg):
        return all(x.satisfied_by(cfg) for x in self.children)

    def partial_satisfy(self, cfg):
        """Returns a new condition where any terms evaluating to true
        under `cfg` are removed. Returns object equivalent to `self`
        if there is no match at all, or ``TrueCondition()`` if there
        is a complete match.
        """
        terms = [child.partial_satisfy(cfg) for child in self.children]
        terms = [term for term in terms if type(term) is not TrueCondition]
        if len(terms) == 0:
            return TrueCondition()
        elif len(terms) == 1:
            return terms[0]
        else:
            return And(terms)

    def _lt_same_type(self, other):
        # list comparison will do fine, since lists should be sorted
        return self.children < other.children

class Match(Condition):
    """AST node for "varname=value" matchers
    """
    def __init__(self, varname, value):
        self.varname = varname
        self.value = value
        self.tuple = (Match, varname, value)
        self._input_vars = frozenset([varname])

    def satisfied_by(self, cfg):
        return (self.varname in cfg and cfg[self.varname] == self.value)

    def get_mentioned_values(self):
        # Extract values to use to infer enums; for now very simple.
        # In time extract limits, e.g., for "1.2 to 3.4", return ["1.2", "3.4"]
        return [self.value]

    def partial_satisfy(self, cfg):
        if self.satisfied_by(cfg):
            return true_condition
        else:
            return self

    def _lt_same_type(self, other):
        return (self.varname, self.value) < (other.varname, other.value)

class Assign(Node):
    """AST node for "attrname: value" and "assign attrname: value"
    """
    def __init__(self, attrname, value):
        self.attrname = attrname
        self.value = value
        self.tuple = (Assign, attrname, value)

    def apply(self, attrs):
        if self.attrname in attrs:
            raise IllegalStackSpecError('"%s" assigned twice' % self.attrname)
        attrs[self.attrname] = self.value

class Extend(Node):
    """AST node for appending a list given a condition"""
    def __init__(self, condition, value_list):
        self.condition = condition
        self.value_list = value_list
        self.tuple = (Extend, condition, value_list)

    def apply(self, obj):
        if type(obj) is not list:
            raise TypeError('expected list for Extend action')
        obj.extend(self.value_list)
        
def iterate_leaves(node):
    """
    Iterates through lists and dicts, iterating the leaves. Dict keys are
    assumed to be boring strings and are not touched.
    """
    if isinstance(node, list):
        for item in node:
            for x in iterate_leaves(item):
                yield x
    elif isinstance(node, dict):
        for item in node.values():
            for x in iterate_leaves(item):
                yield x
    else:
        yield node

_when_re = re.compile('when\s+(.*)=(.*)')
def parse_condition(s):
    """Parses a condition expression node, or returns None if the string is not a match expression/

    Currently only "when varname=value" is supported.
    """
    m = _when_re.match(s)
    if m:
        return Match(m.group(1), m.group(2))
    else:
        return None

def parse_list_with_conditions(doc, under_condition=true_condition):
    result = []
    for item in doc:
        cond = None
        if isinstance(item, dict) and len(item) == 1:
            key, value = item.items()[0]
            cond = parse_condition(key)
            if cond:
                if not isinstance(value, list):
                    raise IllegalStackSpecError('a list condition must contain list items', value)
                parsed_lst = parse_list_with_conditions(value, under_condition & cond)
                result.extend(parsed_lst)
            # else fall through to "if not cond" below    
        elif isinstance(item, dict):
            # just check that none of the items are conditions, then fall through
            for key, value in item.items():
                if parse_condition(key):
                    raise IllegalStackSpecError("conditions in list must all be prepended by '-' "
                                                "(so that order is preserved)")

        if not cond:
            parsed_item = parse_condition_tree(item, under_condition)
            result.append(parsed_item)
    return result


def struct_type(x):
    # the 'structural type' is either dict, list or str
    if isinstance(x, dict):
        return dict
    elif isinstance(x, list):
        return list
    else:
        return str

def merge_parsed_dicts(a, b):
    result = {}
    for key, a_value in a.items():
        if key not in b:
            result[key] = a_value
        else:
            b_value = b[key]
            if isinstance(a_value, dict):
                if not isinstance(b_value, dict):
                    raise IllegalStackSpecError('cannot merge a value with a dict')
                result[key] = merge_parsed_dicts(a_value, b_value)
            else:
                if not (isinstance(a_value, Select) and isinstance(b_value, Select)):
                    raise TypeError('unexpected type in parsed dicts: %r, %r' %
                                    (type(a_value), type(b_value)))
                result[key] = a_value + b_value
    for key, b_value in b.items():
        if key not in a:
            result[key] = b_value
    return result

def parse_dict_with_conditions(doc, under_condition=true_condition):
    result = {}
    # traverse in sorted order, just to make unit tests predictable
    keys = sorted(doc.keys())
    for key in keys:
        value = doc[key]
        cond = parse_condition(key)
        if cond:
            # it wasn't really a dict entry, just a condition marker, so the dict
            # must "continue within"
            if not isinstance(value, dict):
                raise IllegalStackSpecError("dict-style matchers must have dict children; "
                                            "otherwise use list-style mathers", value)
            parsed_result = parse_dict_with_conditions(value, cond & under_condition)
        else:
            parsed_value = parse_condition_tree(value, under_condition)
            parsed_result = {key: parsed_value}
        result = merge_parsed_dicts(result, parsed_result)
    return result

def parse_condition_tree(doc, under_condition=true_condition):
    """
    Parses a tree of dict/list/str so that conditional expressions are made
    available. In the resulting structure:

     - Every dict has a Select as its value
     - Every list is turned from [a, b, ...] to [(cond_a, a), (cond_b, b), ...]
     - str is untouched because it is illegal to insert conditions into strings

    Note that the input match statements must be placed according to the type
    of their parent "value", i.e., if "a" has a list as its value, one does::

        a:
          - include_one=true:
            - 1
          - include_two=true:
            - 2
          - 3

    whereas if "a" has a dict as its value::

        a:
          include_one=true:
            one: 1
          onclude_two=true:
            two: 2
          three: 3
    """
    if isinstance(doc, dict):
        return parse_dict_with_conditions(doc, under_condition)
    elif isinstance(doc, list):
        return parse_list_with_conditions(doc, under_condition)
    else:
        scalar_node = parse_scalar(doc)
        if type(under_condition) is TrueCondition:
            return scalar_node
        else:
            return Select((under_condition, scalar_node))

def select_option(options):
    """Which options out of multiple possible to pick?

    The rule is to a) ensure that all conditions are nested within one
    another, b) pick the most specific one.

    May raise ConditionsNotNested.

    Returns
    -------

    option: (Condition, object)
        Selected option from input list

    """
    def cond_children(cond):
        if type(cond) is And:
            return cond.children
        else:
            return [cond]

    if len(options) == 1:
        return options[0]

    # TrueCondition is least specific
    options = [(cond, val) for cond, val in options if type(cond) is not TrueCondition]
    if len(options) == 0:
        raise ConditionsNotNested("only TrueCondition present, cannot discriminate")

    options.sort(key=lambda option: len(cond_children(option[0])))
    for i in range(len(options) - 1):
        child_cond = options[i][0]
        parent_cond = options[i + 1][0]
        if set(cond_children(child_cond)).difference(cond_children(parent_cond)):
            raise ConditionsNotNested('%r not nested in %r' % (child_cond, parent_cond))
    # OK, they're all nested, select the last (most specific) one
    return options[-1]

def evaluate_dict_with_conditions(rules, cfg, include_keys=None):
    if include_keys:
        rules = dict((key, value) for key, value in rules.items() if key in include_keys)
    result = {}
    for key, value in rules.items():
        if isinstance(value, Select):
            select = value
            # filter for options satisfied by cfg
            options = [(cond, value) for cond, value in select.options
                       if cond.satisfied_by(cfg)]
            if len(options) > 0:
                cond, value = select_option(options)
                result[key] = value
        else:
            value = evaluate_dict_with_conditions(value, cfg)
            result[key] = value
    return result

def evaluate_list_with_conditions(rules, cfg):
    result = []
    for rule in rules:
        assert type(rule) is Extend
        if rule.condition.satisfied_by(cfg):
            rule.apply(result)
    return result

def get_tree_inputs(node):
    inputs = set()
    for leaf in iterate_leaves(node):
        inputs.update(leaf.input_vars())
    return inputs

def insert_tree_in_program(tree, program):
    rules = tree['rules']
    for varname, rhs in rules.items():
        program.add_assignment(varname, rhs)
    return program

def parse_stack_dsl(stream, include_dir=None, encountered=None,
                    under_condition=true_condition,
                    program=None):
    doc = marked_yaml_load(stream)

    def resolve_included_file(basename):
        return pjoin(include_dir, basename) + '.yml'

    if 'include' in doc:
        include_section = doc.get('include', [])
        del doc['include']
    else:
        include_section = []

    result = {}
    include_list = parse_list_with_conditions(include_section)
    if include_list and include_dir is None:
        raise TypeError("No include_dir passed, but spec contains an include section")
    for segment in include_list:
        assert type(segment) is Extend
        child_cond = under_condition & segment.condition
        for basename in segment.value_list:
            include_filename = resolve_included_file(basename)
            included_doc = parse_stack_dsl_file(include_filename, encountered, child_cond)
            result = merge_parsed_dicts(result, included_doc)

    tree = parse_condition_tree(doc, under_condition)
    if program is None:
        program = Program()
    insert_tree_in_program(tree, program)
    return program
    
def parse_stack_dsl_file(filename, encountered=None, under_condition=true_condition):
    if os.path.isdir(filename):
        filename = pjoin(filename, 'stack.yml')
    filename = os.path.realpath(filename)

    if encountered is None:
        encountered = set()
    if filename in encountered:
        raise IllegalStackSpecError("Infinite include loop at %s" % filename)
    encountered.add(filename)

    include_dir = os.path.dirname(filename)
    with open(filename) as f:
        return parse_stack_dsl(f, include_dir, encountered, under_condition)
