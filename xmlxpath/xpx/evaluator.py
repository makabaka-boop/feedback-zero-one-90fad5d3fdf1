"""XPath 1.0 evaluator.

Implements the expression semantics of sections 2-5 of the
recommendation over the node model of :mod:`xpx.xmlmodel`:

* ``and``/``or`` short-circuit;
* step predicates see positions in axis order (reverse axes: ancestor,
  ancestor-or-self, preceding, preceding-sibling use reverse document
  order); FilterExpr predicates see document order;
* node-set comparisons are existential, per section 3.4;
* ``div``/``mod`` follow IEEE 754 (division by zero yields Infinity/NaN).
"""

import math

from . import xmlmodel
from .convert import to_boolean, to_number, to_string
from .errors import QueryError

_INF = float('inf')
_NAN = float('nan')


class Ctx(object):
    __slots__ = ('node', 'pos', 'size')

    def __init__(self, node, pos, size):
        self.node = node
        self.pos = pos
        self.size = size


def evaluate(ast, doc):
    """Evaluate *ast* with the initial context (document node, 1, 1)."""
    return eval_expr(ast, Ctx(doc, 1, 1))


def eval_expr(node, ctx):
    tag = node[0]
    if tag == 'num' or tag == 'str':
        return node[1]
    if tag == 'neg':
        return -to_number(eval_expr(node[1], ctx))
    if tag == 'bin':
        return eval_bin(node[1], node[2], node[3], ctx)
    if tag == 'union':
        return union(eval_expr(node[1], ctx), eval_expr(node[2], ctx))
    if tag == 'call':
        return eval_call(node[1], node[2], ctx)
    if tag == 'path':
        return eval_steps(node[2], [node_doc(ctx)] if node[1] else [ctx.node])
    if tag == 'filter':
        base = eval_expr(node[1], ctx)
        if not isinstance(base, list):
            raise QueryError('type error: filter base is not a node-set')
        nodes = sorted(base, key=lambda n: n.sort_key)
        return apply_predicates(node[2], nodes)
    if tag == 'pathexpr':
        base = eval_expr(node[1], ctx)
        if not isinstance(base, list):
            raise QueryError('type error: path base is not a node-set')
        start = sorted(base, key=lambda n: n.sort_key)
        return eval_steps(node[2], start)
    raise QueryError('internal error: unknown AST node %r' % (node[0],))


def node_doc(ctx):
    return ctx.node.doc


# ---------------------------------------------------------------------------
# location paths

def eval_steps(steps, current):
    for step in steps:
        seen = set()
        nxt = []
        for node in current:
            for r in eval_step(step, node):
                if id(r) not in seen:
                    seen.add(id(r))
                    nxt.append(r)
        current = nxt
    return current


def eval_step(step, node):
    _, axis, nodetest, preds = step
    candidates = xmlmodel.axis_nodes(axis, node)
    tested = [n for n in candidates if match_node_test(nodetest, n, axis)]
    return apply_predicates(preds, tested)


def match_node_test(nodetest, node, axis):
    kind = nodetest[0]
    if kind == 'nt_star':
        # principal node type: attribute for the attribute axis, else element
        if axis == 'attribute':
            return isinstance(node, xmlmodel.Attribute)
        return isinstance(node, xmlmodel.Element)
    if kind == 'nt_name':
        if axis == 'attribute':
            return isinstance(node, xmlmodel.Attribute) \
                and node.name == nodetest[1]
        return isinstance(node, xmlmodel.Element) and node.name == nodetest[1]
    # node type test
    ntype = nodetest[1]
    if ntype == 'node':
        return True
    if ntype == 'text':
        return isinstance(node, xmlmodel.Text)
    # 'comment' and 'processing-instruction': the XML subset forbids them
    return False


def apply_predicates(preds, nodes):
    result = nodes
    for pred in preds:
        size = len(result)
        kept = []
        for i, node in enumerate(result):
            v = eval_expr(pred, Ctx(node, i + 1, size))
            if type(v) is float:
                if v == i + 1:
                    kept.append(node)
            elif to_boolean(v):
                kept.append(node)
        result = kept
    return result


def union(a, b):
    seen = set(id(n) for n in a)
    out = list(a)
    for n in b:
        if id(n) not in seen:
            seen.add(id(n))
            out.append(n)
    return out


# ---------------------------------------------------------------------------
# operators

def eval_bin(op, left, right, ctx):
    if op == 'or':
        if to_boolean(eval_expr(left, ctx)):
            return True
        return to_boolean(eval_expr(right, ctx))
    if op == 'and':
        if not to_boolean(eval_expr(left, ctx)):
            return False
        return to_boolean(eval_expr(right, ctx))
    if op in ('=', '!='):
        return eval_equality(op == '=', left, right, ctx)
    if op in ('<', '<=', '>', '>='):
        return eval_relational(op, left, right, ctx)
    a = to_number(eval_expr(left, ctx))
    b = to_number(eval_expr(right, ctx))
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == 'div':
        return xpath_div(a, b)
    # 'mod'
    return xpath_mod(a, b)


def xpath_div(a, b):
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return _NAN
        return math.copysign(_INF, a) * math.copysign(1.0, b)
    return a / b


def xpath_mod(a, b):
    if math.isnan(a) or math.isnan(b) or math.isinf(a) or b == 0.0:
        return _NAN
    return math.fmod(a, b)


def _compare(op, a, b):
    if op == '<':
        return a < b
    if op == '<=':
        return a <= b
    if op == '>':
        return a > b
    return a >= b


def eval_equality(eq, left, right, ctx):
    lv = eval_expr(left, ctx)
    rv = eval_expr(right, ctx)
    lns = isinstance(lv, list)
    rns = isinstance(rv, list)
    if lns and rns:
        rvals = [xmlmodel.string_value(n) for n in rv]
        for x in lv:
            sx = xmlmodel.string_value(x)
            for sy in rvals:
                if (sx == sy) == eq:
                    return True
        return False
    if lns or rns:
        ns, other = (lv, rv) if lns else (rv, lv)
        if type(other) is bool:
            b = to_boolean(ns)
            return (b == other) if eq else (b != other)
        if type(other) is float:
            for n in ns:
                x = to_number(xmlmodel.string_value(n))
                if (x == other) == eq:
                    return True
            return False
        for n in ns:
            s = xmlmodel.string_value(n)
            if (s == other) == eq:
                return True
        return False
    if type(lv) is bool or type(rv) is bool:
        a, b = to_boolean(lv), to_boolean(rv)
        return (a == b) if eq else (a != b)
    if type(lv) is float or type(rv) is float:
        a, b = to_number(lv), to_number(rv)
        return (a == b) if eq else (a != b)
    a, b = to_string(lv), to_string(rv)
    return (a == b) if eq else (a != b)


def eval_relational(op, left, right, ctx):
    lv = eval_expr(left, ctx)
    rv = eval_expr(right, ctx)
    lns = isinstance(lv, list)
    rns = isinstance(rv, list)
    if lns and rns:
        rnums = [to_number(xmlmodel.string_value(n)) for n in rv]
        for x in lv:
            nx = to_number(xmlmodel.string_value(x))
            for ny in rnums:
                if _compare(op, nx, ny):
                    return True
        return False
    if lns or rns:
        if lns:
            ns, other, flipped = lv, rv, False
        else:
            ns, other, flipped = rv, lv, True
        if type(other) is bool:
            a = to_number(to_boolean(ns))
            b = to_number(other)
            return _compare(op, b, a) if flipped else _compare(op, a, b)
        if type(other) is str:
            other = to_number(other)
        for n in ns:
            x = to_number(xmlmodel.string_value(n))
            if _compare(op, other, x) if flipped else _compare(op, x, other):
                return True
        return False
    return _compare(op, to_number(lv), to_number(rv))


# ---------------------------------------------------------------------------
# functions

def eval_call(name, args, ctx):
    if name == 'position':
        return float(ctx.pos)
    if name == 'last':
        return float(ctx.size)
    if name == 'count':
        v = eval_expr(args[0], ctx)
        if not isinstance(v, list):
            raise QueryError('type error: count() needs a node-set')
        return float(len(v))
    if name == 'string':
        if args:
            return to_string(eval_expr(args[0], ctx))
        return xmlmodel.string_value(ctx.node)
    if name == 'number':
        if args:
            return to_number(eval_expr(args[0], ctx))
        return to_number(xmlmodel.string_value(ctx.node))
    if name == 'boolean':
        return to_boolean(eval_expr(args[0], ctx))
    if name == 'not':
        return not to_boolean(eval_expr(args[0], ctx))
    raise QueryError('unknown function: %s()' % name)
