import os
from os.path import join as pjoin

from ..deps import yaml

class IllegalStackSpecError(Exception):
    pass

class ConditionsNotNested(IllegalStackSpecError):
    pass

class AstNode(object):
    def __hash__(self):
        return hash(self.tuple)

    def __eq__(self, other):
        if not isinstance(other, AstNode):
            return False
        return self.tuple == other.tuple

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        cls = self.tuple[0]
        return '%s(%s)' % (cls.__name__, ', '.join(repr(arg) for arg in self.tuple[1:]))

class Select(AstNode):
    def __init__(self, *options):
        # Always turn Select(Selection([a], [b]), [c]) to Select([a, b, c])
        def flatten(x):
            if type(x) is Select:
                return x.options
            else:
                return [x]
        self.options = options = sum([flatten(x) for x in options], [])
        self.tuple = (Select, options)

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

class Condition(AstNode):
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
        self.tuple = (And, children)

    def __repr__(self):
        if len(self.children) <= 1:
            return 'And(%s)' % repr(self.children)
        else:
            return ' & '.join(repr(x) for x in self.children)

    def satisfied_by(self, cfg):
        return all(x.satisfied_by(cfg) for x in self.children)

class Match(Condition):
    """AST node for "varname=value" matchers
    """
    def __init__(self, varname, value):
        self.varname = varname
        self.value = value
        self.tuple = (Match, varname, value)

    def satisfied_by(self, cfg):
        return (self.varname in cfg and cfg[self.varname] == self.value)

class Assign(AstNode):
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

class Extend(AstNode):
    """AST node for appending a list given a condition"""
    def __init__(self, condition, value_list):
        self.condition = condition
        self.value_list = value_list
        self.tuple = (Extend, condition, value_list)

    def apply(self, obj):
        if type(obj) is not list:
            raise TypeError('expected list for Extend action')
        obj.extend(self.value_list)
        

def parse_condition(s):
    """Parses a condition expression node, or returns None if the string is not a match expression/

    Currently only "varname=value" is supported, but "1.0<=version<1.4" etc.
    may follow.
    """
    if '=' in s:
        if s.count('=') != 1:
            raise IllegalStackSpecError('= encountered more than once in %s' % s)
        return Match(*s.split('='))
    else:
        return None

## def parse_action(key, value):
##     """Parses "attr: value" nodes in the rules

##     Currently only "x" and "assign x" (the same) are supported.
##     """
##     words = key.split()
##     if len(words) > 2:
##         raise IllegalStackSpecError('More than two words in "%s"' % s)
##     elif len(words) == 2:
##         action, attrname = words
##         if action == 'set':
##             return attrname, Assign(attrname, value)
##         else:
##             raise IllegalStackSpecError('Unknown action: %s' % s)
##     else:
##         return key, Assign(key, value)

def parse_list_with_conditions(doc, parent_condition=true_condition, result=None):
    result = result if result is not None else []
    buffer = []
    def emit_buffer():
        # use a buffer to string together items with the same condition
        if len(buffer):
            result.append(Extend(parent_condition, list(buffer)))
        del buffer[:]

    for item in doc:
        if isinstance(item, dict):
            # broken up by condition; emit anything currently in buffer
            emit_buffer()
            
            if len(item) == 1:
                key, value = item.items()[0]
                cond = parse_condition(key)
                if cond:
                    parse_list_with_conditions(value, parent_condition & cond, result)
                else:
                    raise IllegalStackSpecError('dict within list not currently supported/needed')
            else:
                for key, value in item.items():
                    if parse_condition(key):
                        raise IllegalStackSpecError("conditions in list must all be prepended by '-' "
                                                    "(so that order is preserved)")
        elif isinstance(item, list):
            raise IllegalStackSpecError('list within list not currently supported/needed')
        else:
            buffer.append(item)
    emit_buffer()
    return result

def parse_dict_with_conditions(doc, parent_condition=true_condition):
    """Turns a tree of conditions/selectors and attribute actions into a list

    Turns::

        project=foo:
            version=bar:
                a: 1
            b: 2
        a: 3
        c: 4

    Into::

        {"a": [([Match("project", "foo"), Match("version", "bar")], Assign(1)),
               ...],
         ...}
    """
    result = {}
    # traverse in sorted order, just to make unit tests predictable
    keys = sorted(doc.keys())
    for key in keys:
        value = doc[key]
        cond = parse_condition(key)
        if cond:
            if not isinstance(value, dict):
                raise IllegalStackSpecError('child of condition "%s" not a dict' % cond)
            recurse_result = parse_dict_with_conditions(value, parent_condition & cond)
            for merge_key, merge_select in recurse_result.items():
                result[merge_key] = result.get(merge_key, None) + merge_select
        elif isinstance(value, dict):
            raise IllegalStackSpecError('nested dicts not currently supported/needed')
        else:
            select = Select((parent_condition, value)) + result.get(key, None)
            result[key] = select
    return result

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

def evaluate_dict_with_conditions(rules, cfg):
    result = {}
    for key, select in rules.items():
        assert type(select) is Select
        # filter for options satisfied by cfg
        options = [(cond, value) for cond, value in select.options
                   if cond.satisfied_by(cfg)]
        if len(options) > 0:
            option = select_option(options)
            result[key] = option[1]
    return result

def evaluate_list_with_conditions(rules, cfg):
    result = []
    for rule in rules:
        assert type(rule) is Extend
        if rule.condition.satisfied_by(cfg):
            rule.apply(result)
    return result

def parse_stack_spec(filename, encountered=None, parent_condition=true_condition):
    """
    Loads stack spec files
    """
    if encountered is None:
        encountered = set()
    if os.path.isdir(filename):
        filename = pjoin(filename, 'stack.yml')
    filename = os.path.realpath(filename)
    if filename in encountered:
        raise IllegalStackSpecError("Infinite include loop at %s" % filename)
    encountered.add(filename)
    dir_name = os.path.dirname(filename)
    with open(filename) as f:
        doc = yaml.safe_load(f)

    def resolve_included_file(basename):
        return pjoin(dir_name, basename) + '.yml'

    if 'include' in doc:
        include_section = doc.get('include', [])
        del doc['include']
    else:
        include_section = []
    
    # two-level dicts explicitly; should probably extend to n-level
    # inside of parse_dict_with_conditions in time
    result = {}
    for section, section_doc in doc.items():
        if not isinstance(section_doc, dict):
            raise IllegalStackSpecError('%s section should be a dict' % value)
        result[section] = parse_dict_with_conditions(section_doc, parent_condition)

    # merge in included sections (easier to do this last, and order should not matter
    # by definition)
    include_list = parse_list_with_conditions(include_section)
    for segment in include_list:
        assert type(segment) is Extend
        child_cond = parent_condition & segment.condition
        for basename in segment.value_list:
            included_doc = parse_stack_spec(resolve_included_file(basename),
                                            encountered,
                                            child_cond)
            for section, section_doc in included_doc.items():
                section_result = result.setdefault(section, {})
                
                for key, value in section_doc.items():
                    if key in section_result:
                        section_result[key] = section_result.get(key, None) + value
                    else:
                        section_result[key] = value

    return result
