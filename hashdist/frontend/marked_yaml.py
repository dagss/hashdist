"""
A PyYAML loader subclass that is fit for parsing DSLs: It annotates
positions in source code, and only parses values as strings.

The loader is based on `SafeConstructor`, i.e., the behaviour of
`yaml.safe_load`, but in addition:

 - Every dict/list/unicode is replaced with dict_node/list_node/unicode_node,
   which subclasses dict/list/unicode to add the attributes `start_mark`
   and `end_mark`. (See the yaml.error module for the `Mark` class.)

 - Every string is always returned as unicode, no ASCII-ficiation is
   attempted.

 - Note that only string content is ever returned (uses BaseResolver rather
   than Resolver)
"""

import re

from hashdist.deps.yaml.composer import Composer
from hashdist.deps.yaml.reader import Reader
from hashdist.deps.yaml.scanner import Scanner
from hashdist.deps.yaml.composer import Composer
from hashdist.deps.yaml.resolver import BaseResolver
from hashdist.deps.yaml.parser import Parser
from hashdist.deps.yaml.constructor import Constructor, BaseConstructor, SafeConstructor
from hashdist.deps.yaml.nodes import MappingNode

#
# Nodes of returned AST
#
class Expr:
    def __init__(self, value, start_mark, end_mark):
        self.value = value
        self.start_mark = start_mark
        self.end_mark = end_mark

    def __repr__(self):
        return 'Expr(%r)' % self.value

def create_node_class(cls):
    class node_class(cls):
        def __init__(self, x, start_mark, end_mark):
            cls.__init__(self, x)
            self.start_mark = start_mark
            self.end_mark = end_mark

        def __new__(self, x, start_mark, end_mark):
            return cls.__new__(self, x)
    node_class.__name__ = '%s_node' % cls.__name__
    return node_class

dict_node = create_node_class(dict)
list_node = create_node_class(list)
unicode_node = create_node_class(unicode)

STACK_EXPR_TAG = u'tag:github.com/hashdist,2013:stack-desc-expr'

#
# tag resolver
#

class HdistResolver(BaseResolver):
    # we do the path resolution ourselves and override descend/ascend
    def __init__(self):
        self.mapping_path = []
        self.did_push = []
    
    def descend_resolver(self, current_node, current_index):
        if isinstance(current_node, MappingNode) and current_index is not None:
            print 'VALUE'
            self.mapping_path.append(current_index.value)
            self.did_push.append(True)
        else:
            print 'OTHER'
            self.did_push.append(False)

    def ascend_resolver(self):
        should_pop = self.did_push.pop()
        if should_pop:
            self.mapping_path.pop()
        print 'POP'
        
    def resolve(self, kind, value, implicit):
        tag = BaseResolver.resolve(self, kind, value, implicit)
        print tag, value, self.mapping_path
        if tag == STACK_EXPR_TAG and len(self.mapping_path) <= 1:
            # first levels are section names
            print tag, self.mapping_path
            return u'tag:yaml.org,2002:str'
        return tag


HdistResolver.add_implicit_resolver(
    u'tag:yaml.org,2002:bool',
    re.compile(ur'''^(?:true|false)$''', re.X),
    list(u'tf'))

HdistResolver.add_implicit_resolver(
        u'tag:yaml.org,2002:null',
        re.compile(ur'''^(?:null| )$''', re.X),
        [u'n', u''])

HdistResolver.add_implicit_resolver(
        u'tag:yaml.org,2002:int',
        re.compile(ur'''^(?:[-+]?0b[0-1_]+
                    |[-+]?0[0-7_]+
                    |[-+]?(?:0|[1-9][0-9_]*)
                    |[-+]?0x[0-9a-fA-F_]+
                    |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$''', re.X),
        list(u'-+0123456789'))

HdistResolver.add_implicit_resolver(
        STACK_EXPR_TAG,
        re.compile(ur'''^(?:[a-zA-Z_-].*)$''', re.X),
        [unicode(chr(i)) for i in range(ord('a'), ord('z') + 1) + range(ord('A'), ord('Z') + 1)] +
        [u"-", u"_"])


#
# node constructor
#
class NodeConstructor(SafeConstructor):
    # To support lazy loading, the original constructors first yield
    # an empty object, then fill them in when iterated. Due to
    # laziness we omit this behaviour (and will only do "deep
    # construction") by first exhausting iterators, then yielding
    # copies.
    def construct_yaml_map(self, node):
        obj, = SafeConstructor.construct_yaml_map(self, node)
        return dict_node(obj, node.start_mark, node.end_mark)

    def construct_yaml_seq(self, node):
        obj, = SafeConstructor.construct_yaml_seq(self, node)
        return list_node(obj, node.start_mark, node.end_mark)

    def construct_yaml_str(self, node):
        obj = SafeConstructor.construct_scalar(self, node)
        assert isinstance(obj, unicode)
        return unicode_node(obj, node.start_mark, node.end_mark)

    def construct_yaml_expr(self, node):
        obj = SafeConstructor.construct_scalar(self, node)
        assert isinstance(obj, unicode)
        return Expr(obj, node.start_mark, node.end_mark)

NodeConstructor.add_constructor(
        u'tag:yaml.org,2002:map',
        NodeConstructor.construct_yaml_map)

NodeConstructor.add_constructor(
        u'tag:yaml.org,2002:seq',
        NodeConstructor.construct_yaml_seq)

NodeConstructor.add_constructor(
        u'tag:yaml.org,2002:str',
        NodeConstructor.construct_yaml_str)

NodeConstructor.add_constructor(
        STACK_EXPR_TAG,
        NodeConstructor.construct_yaml_expr)

#
# loader
#

# Use BaseResolver to avoid parsing the string nodes
class MarkedLoader(Reader, Scanner, Parser, Composer, NodeConstructor, HdistResolver):
    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        HdistResolver.__init__(self)

def marked_yaml_load(stream):
    return MarkedLoader(stream).get_single_data()
