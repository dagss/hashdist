import os
import re

import hashdist.deps.pyparsing as pp

class Term(object):
    is_string = is_brace = is_single_star = is_double_star = False

    def __eq__(self, other):
        return type(self) is type(other)
    
    def __ne__(self, other):
        return not self == other

class BraceTerm(Term):
    is_brace = True
    
    def __init__(self, terms):
        self.terms = terms

    @staticmethod
    def parse(toks):
        return BraceTerm(toks[0].split(','))

    def __repr__(self):
        return 'BraceTerm(%r)' % self.terms

    def __eq__(self, other):
        return type(other) is BraceTerm and self.terms == other.terms

class StringTerm(Term):
    is_string = True
    
    def __init__(self, string):
        self.string = string

    @staticmethod
    def parse(toks):
        return StringTerm(''.join(toks))
    
    def __repr__(self):
        return 'StringTerm("%s")' % self.string

    def __eq__(self, other):
        return type(other) is StringTerm and self.string == other.string

class _SingleStar(Term):
    is_single_star = True
    
    def __repr__(self):
        return 'single_star'
single_star = _SingleStar()

class _DoubleStar(Term):
    is_double_star = True
    
    def __repr__(self):
        return 'double_star'
double_star = _DoubleStar()

def handle_concat_witin_pathcomp(toks):
    return toks

def handle_slash(toks):
    return toks[0]

def create_pattern_expr():
    # apologies for the quality of this parser...
    
    slash = pp.Suppress('/')
    lbrace = pp.Suppress('{')
    rbrace = pp.Suppress('}')

    escaped_char = pp.Combine("\\" + pp.oneOf(list(pp.printables)))

    brace_group = pp.Combine(lbrace + pp.SkipTo(rbrace,ignore=escaped_char) + rbrace)
    brace_group.setParseAction(BraceTerm.parse)

    literal_char = pp.oneOf([x for x in pp.printables if x not in '{}\\/*'])

    single_star_p = pp.Literal('*') + ~pp.FollowedBy('*')
    single_star_p.setParseAction(lambda toks: single_star)
    double_star_p = pp.Literal('**')
    double_star_p.setParseAction(lambda toks: double_star)

    str_group = pp.OneOrMore(escaped_char | literal_char)
    str_group.setParseAction(StringTerm.parse)

    term = str_group | brace_group | single_star_p | double_star_p

    expr = pp.operatorPrecedence(term, [
        (None, 2, pp.opAssoc.LEFT, handle_concat_witin_pathcomp),
        (slash, 2, pp.opAssoc.LEFT, handle_slash),
        ])

    return expr

_pattern_expr = create_pattern_expr()

def parse_glob(x):
    is_abs = x.startswith('/')
    if is_abs:
        x = x[1:]
    path = _pattern_expr.parseString(x)
    path = path.asList()
    # compound terms are lists, the others single objects; turn all into lists
    path = [[x] if not isinstance(x, list) else x for x in path]
    return is_abs, path



def glob(glob):
    """globbing used in symlink DSL

    This will gradually evolve to include features needed on a case-by-case basis

    Note: This should perhaps be replaced by something that already exists, but couldn't
    find anything that fit the bill (at least non-GPL).

    Currently supported
    -------------------

     - ``*.ext``
     - ``/bin/{cp,ls,true,false}`` (but not together with * in same path-part)
     - ``\{`` and ``\}`` escapes the { and } characters

    Parameters
    ----------

    glob : str
        Glob pattern (see above)

    """
    parts = os.path.split(glob)
    for part in parts:
        cstart = CURLY_START_RE.search(part)
        if cstart and '*' in part:
            raise NotImplementedError('Cannot use {} and * together currently')
        if cstart:
            cstop = CURLY_STOP_RE.search(part)
            if cstop.start() <= cstart.start():
                raise ValueError('Unmatched }')
            
            
            
        pass
        #part.re
        #if '*' in part and '{
