"""XPath 1.0 parser (grammar sections 2-5 of the recommendation).

Produces a tuple-based AST::

    ('num', float) ('str', str)
    ('call', name, [args])
    ('path', absolute, [step])           location path
    ('step', axis, nodetest, [pred])
    ('nt_name', name) ('nt_star',) ('nt_type', kind, literal_or_None)
    ('filter', base, [pred])             FilterExpr
    ('pathexpr', base, [step])           FilterExpr (//?) RelativeLocationPath
    ('union', a, b)
    ('bin', op, a, b)                    or/and/=/!=/</<=/>/>=/+/-/*/div/mod
    ('neg', a)

Out-of-subset constructs (variables, prefixed names, the namespace axis)
are rejected by the lexer or here; function names and arities are checked
by :mod:`xpx.checker`.
"""

from .errors import QueryError
from .lexer import AXIS_NAMES, NODE_TYPES, tokenize

DOS_STEP = ('step', 'descendant-or-self', ('nt_type', 'node', None), ())

_STEP_STARTERS = ('DOT', 'DDOT', 'AT', 'STAR', 'NAME')


def parse(q):
    """Parse query string *q* into an AST; raise :class:`QueryError`."""
    parser = _Parser(tokenize(q))
    expr = parser.parse_expr()
    tok = parser.peek()
    if tok.kind != 'EOF':
        raise QueryError('unexpected %s after expression' % _describe(tok))
    return expr


def _describe(tok):
    if tok.kind == 'EOF':
        return 'end of expression'
    if tok.val is None:
        return tok.kind
    return '%s %r' % (tok.kind, tok.val)


class _Parser(object):
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def next(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def expect(self, kind):
        tok = self.next()
        if tok.kind != kind:
            raise QueryError('expected %s, found %s'
                             % (kind, _describe(tok)))
        return tok

    # -- expressions (grammar [12]-[25]) ---------------------------------
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek().kind == 'OP' and self.peek().val == 'or':
            self.next()
            left = ('bin', 'or', left, self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_equality()
        while self.peek().kind == 'OP' and self.peek().val == 'and':
            self.next()
            left = ('bin', 'and', left, self.parse_equality())
        return left

    def parse_equality(self):
        left = self.parse_relational()
        while self.peek().kind in ('EQ', 'NE'):
            op = '=' if self.next().kind == 'EQ' else '!='
            left = ('bin', op, left, self.parse_relational())
        return left

    def parse_relational(self):
        left = self.parse_additive()
        ops = {'LT': '<', 'LE': '<=', 'GT': '>', 'GE': '>='}
        while self.peek().kind in ops:
            op = ops[self.next().kind]
            left = ('bin', op, left, self.parse_additive())
        return left

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.peek().kind in ('PLUS', 'MINUS'):
            op = '+' if self.next().kind == 'PLUS' else '-'
            left = ('bin', op, left, self.parse_multiplicative())
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok.kind == 'MULT':
                self.next()
                left = ('bin', '*', left, self.parse_unary())
            elif tok.kind == 'OP' and tok.val in ('div', 'mod'):
                self.next()
                left = ('bin', tok.val, left, self.parse_unary())
            else:
                return left

    def parse_unary(self):
        if self.peek().kind == 'MINUS':
            self.next()
            return ('neg', self.parse_unary())
        return self.parse_union()

    def parse_union(self):
        left = self.parse_path_expr()
        while self.peek().kind == 'PIPE':
            self.next()
            left = ('union', left, self.parse_path_expr())
        return left

    # -- paths (grammar [1]-[11], [17], [18]) -----------------------------
    def parse_path_expr(self):
        tok = self.peek()
        kind = tok.kind
        if kind in ('SLASH', 'DSLASH', 'DOT', 'DDOT', 'AT', 'STAR'):
            return self.parse_location_path()
        if kind == 'NAME':
            nxt = self.peek(1)
            if nxt.kind == 'DCOLON':
                return self.parse_location_path()
            if nxt.kind == 'LPAREN':
                if tok.val in NODE_TYPES:
                    return self.parse_location_path()
                return self.parse_filter_path()
            return self.parse_location_path()
        if kind in ('LPAREN', 'LITERAL', 'NUMBER'):
            return self.parse_filter_path()
        raise QueryError('unexpected %s' % _describe(tok))

    def parse_filter_path(self):
        base = self.parse_primary()
        preds = self.parse_predicates()
        if preds:
            base = ('filter', base, preds)
        if self.peek().kind in ('SLASH', 'DSLASH'):
            return ('pathexpr', base, self.parse_step_tail())
        return base

    def parse_primary(self):
        tok = self.next()
        if tok.kind == 'LPAREN':
            expr = self.parse_expr()
            self.expect('RPAREN')
            return expr
        if tok.kind == 'LITERAL':
            return ('str', tok.val)
        if tok.kind == 'NUMBER':
            return ('num', tok.val)
        if tok.kind == 'NAME' and self.peek().kind == 'LPAREN':
            name = tok.val
            if name in NODE_TYPES:
                raise QueryError('%s() is a node type, not a function' % name)
            self.next()  # consume '('
            args = []
            if self.peek().kind != 'RPAREN':
                args.append(self.parse_expr())
                while self.peek().kind == 'COMMA':
                    self.next()
                    args.append(self.parse_expr())
            self.expect('RPAREN')
            return ('call', name, args)
        raise QueryError('unexpected %s' % _describe(tok))

    def parse_location_path(self):
        tok = self.peek()
        if tok.kind == 'SLASH':
            self.next()
            if self.peek().kind in _STEP_STARTERS:
                return ('path', True, self.parse_relative())
            return ('path', True, [])
        if tok.kind == 'DSLASH':
            self.next()
            return ('path', True, [DOS_STEP] + self.parse_relative())
        return ('path', False, self.parse_relative())

    def parse_relative(self):
        steps = [self.parse_step()]
        while self.peek().kind in ('SLASH', 'DSLASH'):
            if self.next().kind == 'DSLASH':
                steps.append(DOS_STEP)
            steps.append(self.parse_step())
        return steps

    def parse_step_tail(self):
        # one or more "/ Step" / "// Step" groups (used after a FilterExpr)
        steps = []
        while True:
            kind = self.peek().kind
            if kind == 'DSLASH':
                self.next()
                steps.append(DOS_STEP)
            elif kind == 'SLASH':
                self.next()
            else:
                break
            steps.append(self.parse_step())
        return steps

    # -- steps -------------------------------------------------------------
    def parse_step(self):
        tok = self.peek()
        if tok.kind == 'DOT':
            self.next()
            return ('step', 'self', ('nt_type', 'node', None), ())
        if tok.kind == 'DDOT':
            self.next()
            return ('step', 'parent', ('nt_type', 'node', None), ())
        axis = 'child'
        if tok.kind == 'AT':
            self.next()
            axis = 'attribute'
        elif tok.kind == 'NAME' and self.peek(1).kind == 'DCOLON':
            name = tok.val
            self.next()
            self.next()
            if name == 'namespace':
                raise QueryError('namespace axis is not supported')
            if name not in AXIS_NAMES:
                raise QueryError('unknown axis: %s' % name)
            axis = name
        nodetest = self.parse_node_test()
        preds = self.parse_predicates()
        return ('step', axis, nodetest, preds)

    def parse_node_test(self):
        tok = self.next()
        if tok.kind == 'STAR':
            return ('nt_star',)
        if tok.kind == 'NAME':
            if self.peek().kind == 'LPAREN':
                if tok.val not in NODE_TYPES:
                    raise QueryError('unknown node type: %s()' % tok.val)
                self.next()  # consume '('
                if tok.val == 'processing-instruction' \
                        and self.peek().kind == 'LITERAL':
                    literal = self.next().val
                    self.expect('RPAREN')
                    return ('nt_type', 'pi', literal)
                self.expect('RPAREN')
                return ('nt_type', tok.val, None)
            return ('nt_name', tok.val)
        raise QueryError('expected a node test, found %s' % _describe(tok))

    def parse_predicates(self):
        preds = []
        while self.peek().kind == 'LBRACK':
            self.next()
            preds.append(self.parse_expr())
            self.expect('RBRACK')
        return preds
