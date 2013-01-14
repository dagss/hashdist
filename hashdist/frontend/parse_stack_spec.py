import os
from os.path import join as pjoin
from ..deps import yaml

class IllegalStackSpecError(Exception):
    pass


class AstNode(object):
    def __eq__(self, other):
        return self.tuple == other.tuple

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        cls, args = self.tuple[0], self.tuple[1:]
        return '%s(%s)' % (cls.__name__, ', '.join('%r' % arg for arg in args))

class Match(AstNode):
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

def parse_expression(s):
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

def parse_action(key, value):
    """Parses "attr: value" nodes in the rules

    Currently only "x" and "assign x" (the same) are supported.
    """
    words = key.split()
    if len(words) > 2:
        raise IllegalStackSpecError('More than two words in "%s"' % s)
    elif len(words) == 2:
        action, attrname = words
        if action == 'set':
            return attrname, Assign(attrname, value)
        else:
            raise IllegalStackSpecError('Unknown action: %s' % s)
    else:
        return key, Assign(key, value)

def parse_dict_with_rules(doc):
    """Given the YAML-parsed strings, to the extra-interpretation of rules and actions

    Results in a new document with the same rule nesting structure, but with
    strings replaced with AST nodes
    """
    result = []
    for key, value in doc.items():
        expr = parse_expression(key)
        if expr:
            result.append((expr, parse_dict_with_rules(value)))
        else:
            attrname, action = parse_action(key, value)
            result.append((None, action))
    return result

def parse_list_with_rules(doc):
    """Given the YAML-parsed strings, to the extra-interpretation of rules and actions

    Results in a new document with the same rule nesting structure, but with
    strings replaced with AST nodes
    """
    if not type(doc) is list:
        raise IllegalStackSpecError('expected list but found %r' % type(doc))

    result = []
    for item in doc:
        if isinstance(item, dict):
            if len(item) != 1:
                raise IllegalStackSpecError("on rule per item when using rules within lists")
            key, value = item.items()[0]
            expr = parse_expression(key)
            if not expr:
                result.append((None, item))
            else:
                result.append((expr, parse_list_with_rules(value)))
        else:
            result.append((None, item))
    return result

def evaluate_dict_with_rules(rules, cfg, attrs=None):
    """Evaluates the rules given variables in `cfg` to produce a resulting dict

    We evaluate in the tree-form provided by the user, since this allows
    for some cut-offs (and finding an optimal tree-form for the expressions
    seems very overkill).

    Parameters
    ----------

    rules : list
        Syntax tree in format emitted by `parse_rules_doc`
    """
    if attrs is None:
        attrs = {}
    for rule in rules:
        expr, arg = rule
        if expr is None:
            action = arg
            action.apply(attrs)
        elif expr.satisfied_by(cfg):
            children = arg
            assert isinstance(children, list)
            evaluate_dict_with_rules(children, cfg, attrs)
    return attrs
            
def evaluate_list_with_rules(rules, cfg, out_list=None):
    """Evaluates the rules given variables in `cfg` to produce a resulting list

    Parameters
    ----------

    rules : list
        Syntax tree in format emitted by `parse_rules_doc`
    """
    if out_list is None:
        out_list = []
    for rule in rules:
        expr, arg = rule
        if expr is None:
            out_list.append(arg)
        elif expr.satisfied_by(cfg):
            children = arg
            assert isinstance(children, list)
            evaluate_list_with_rules(children, cfg, out_list)
    return out_list


def recursive_load(filename, encountered=None):
    """
    Loads YAML-files, following the '/include' attribute
    """
    if encountered is None:
        encountered = set()
    if os.path.isdir(filename):
        filename += 'stack.yml'
    filename = os.path.realpath(filename)
    if filename in encountered:
        raise IllegalStackSpecError("Inifinite include loop")
    encountered.add(filename)
    dir_name = os.path.dirname(filename)
    with open(filename) as f:
        doc = yaml.safe_load(f)
    docs = []
    for include in doc.get('include', ()):
        included_filename = pjoin(dir_name, include) + '.yml'
        if not os.path.isfile(included_filename):
            raise IllegalStackSpecError('Included file "%s" not found')
        parse_stack_spec(included_filename, encountered)
    return docs

def parse_stack_spec(filename):
    docs = recursive_load(filename)
    doc = merge_docs(docs)
    return doc
