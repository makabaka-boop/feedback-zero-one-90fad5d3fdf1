"""XPath 1.0 tokenizer.

Implements the lexical rules of the XPath 1.0 recommendation, including
the disambiguation rules of its "Lexical Structure" section:

* ``*`` is a multiply operator unless the previous token is one of
  ``@``, ``::``, ``(``, ``[``, ``,`` or an operator (or there is no
  previous token) -- then it is a NameTest wildcard;
* ``and``/``or``/``mod``/``div`` are operator names under the same rule,
  otherwise they are ordinary names (so ``/and`` selects an element
  named ``and``);
* ``.``/``..`` are single tokens; a ``.`` followed by a digit starts a
  number.

Variables (``$``) and prefixed names (a bare ``:``) are rejected here
because they are outside the supported subset.
"""

from .errors import QueryError

AXIS_NAMES = frozenset([
    'ancestor', 'ancestor-or-self', 'attribute', 'child', 'descendant',
    'descendant-or-self', 'following', 'following-sibling', 'parent',
    'preceding', 'preceding-sibling', 'self',
])
NODE_TYPES = frozenset(['comment', 'text', 'processing-instruction', 'node'])
OP_WORDS = frozenset(['and', 'or', 'mod', 'div'])

# Previous-token kinds after which ``*`` is a wildcard and and/or/mod/div
# are plain names: "@", "::", "(", "[", "," and every operator.
_SPECIAL_PREV = frozenset([
    None, 'AT', 'DCOLON', 'LPAREN', 'LBRACK', 'COMMA', 'OP',
    'SLASH', 'DSLASH', 'PIPE', 'PLUS', 'MINUS', 'EQ', 'NE',
    'LT', 'LE', 'GT', 'GE', 'MULT',
])


class Tok(object):
    __slots__ = ('kind', 'val')

    def __init__(self, kind, val=None):
        self.kind = kind
        self.val = val

    def __repr__(self):
        return 'Tok(%r, %r)' % (self.kind, self.val)


def _is_name_start(c):
    # XML 1.0 (5th edition) NameStartChar, excluding ':'
    o = ord(c)
    if o < 0x80:
        return c == '_' or 'a' <= c <= 'z' or 'A' <= c <= 'Z'
    return (0xC0 <= o <= 0xD6 or 0xD8 <= o <= 0xF6 or 0xF8 <= o <= 0x2FF
            or 0x370 <= o <= 0x37D or 0x37F <= o <= 0x1FFF
            or 0x200C <= o <= 0x200D or 0x2070 <= o <= 0x218F
            or 0x2C00 <= o <= 0x2FEF or 0x3001 <= o <= 0xD7FF
            or 0xF900 <= o <= 0xFDCF or 0xFDF0 <= o <= 0xFFFD
            or 0x10000 <= o <= 0xEFFFF)


def _is_name_char(c):
    # XML 1.0 (5th edition) NameChar, excluding ':'
    if _is_name_start(c):
        return True
    o = ord(c)
    if o < 0x80:
        return c in '-.' or '0' <= c <= '9'
    return o == 0xB7 or 0x300 <= o <= 0x36F or 0x203F <= o <= 0x2040


def tokenize(q):
    toks = []
    i, n = 0, len(q)
    prev = None
    while i < n:
        c = q[i]
        if c in ' \t\r\n':
            i += 1
            continue
        two = q[i:i + 2]
        if two == '//':
            toks.append(Tok('DSLASH')); i += 2
        elif two == '..':
            toks.append(Tok('DDOT')); i += 2
        elif two == '::':
            toks.append(Tok('DCOLON')); i += 2
        elif two == '!=':
            toks.append(Tok('NE')); i += 2
        elif two == '<=':
            toks.append(Tok('LE')); i += 2
        elif two == '>=':
            toks.append(Tok('GE')); i += 2
        elif c == '/':
            toks.append(Tok('SLASH')); i += 1
        elif c == '[':
            toks.append(Tok('LBRACK')); i += 1
        elif c == ']':
            toks.append(Tok('RBRACK')); i += 1
        elif c == '(':
            toks.append(Tok('LPAREN')); i += 1
        elif c == ')':
            toks.append(Tok('RPAREN')); i += 1
        elif c == '@':
            toks.append(Tok('AT')); i += 1
        elif c == ',':
            toks.append(Tok('COMMA')); i += 1
        elif c == '|':
            toks.append(Tok('PIPE')); i += 1
        elif c == '+':
            toks.append(Tok('PLUS')); i += 1
        elif c == '-':
            toks.append(Tok('MINUS')); i += 1
        elif c == '=':
            toks.append(Tok('EQ')); i += 1
        elif c == '<':
            toks.append(Tok('LT')); i += 1
        elif c == '>':
            toks.append(Tok('GT')); i += 1
        elif c == '*':
            toks.append(Tok('STAR' if prev in _SPECIAL_PREV else 'MULT'))
            i += 1
        elif c == '$':
            raise QueryError('variables are not supported')
        elif c == ':':
            raise QueryError('prefixed names are not supported')
        elif c == '"' or c == "'":
            j = q.find(c, i + 1)
            if j < 0:
                raise QueryError('unterminated literal')
            toks.append(Tok('LITERAL', q[i + 1:j]))
            i = j + 1
        elif c.isdigit() or (c == '.' and i + 1 < n and q[i + 1].isdigit()):
            j = i
            while j < n and q[j].isdigit():
                j += 1
            if j < n and q[j] == '.':
                j += 1
                while j < n and q[j].isdigit():
                    j += 1
            toks.append(Tok('NUMBER', float(q[i:j])))
            i = j
        elif c == '.':
            toks.append(Tok('DOT')); i += 1
        elif _is_name_start(c):
            j = i + 1
            while j < n and _is_name_char(q[j]):
                j += 1
            word = q[i:j]
            if word in OP_WORDS and prev not in _SPECIAL_PREV:
                toks.append(Tok('OP', word))
            else:
                toks.append(Tok('NAME', word))
            i = j
        else:
            raise QueryError('unexpected character %r' % (c,))
        prev = toks[-1].kind
    toks.append(Tok('EOF'))
    return toks
