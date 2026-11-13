"""Static validation of parsed XPath expressions.

Runs after parsing and before any evaluation ("先验全式语法及子集，再求值"):

* only the seven supported functions may be called, with the arities
  defined by the recommendation (position/last: 0, count: 1,
  string/number: 0 or 1, boolean/not: 1);
* static type checking: union operands, filter/path bases and the
  argument of count() must be node-sets; the whole expression must
  evaluate to a node-set.
"""

from .errors import QueryError

# name -> (min args, max args, result type)
FUNCTIONS = {
    'position': (0, 0, 'number'),
    'last': (0, 0, 'number'),
    'count': (1, 1, 'number'),
    'string': (0, 1, 'string'),
    'number': (0, 1, 'number'),
    'boolean': (1, 1, 'boolean'),
    'not': (1, 1, 'boolean'),
}

_BOOL_OPS = ('or', 'and', '=', '!=', '<', '<=', '>', '>=')


def check(ast):
    """Validate *ast*; raise :class:`QueryError` on any violation."""
    result = _type_of(ast)
    if result != 'nodeset':
        raise QueryError(
            'type error: expression result is %s, not a node-set' % result)


def _require_nodeset(node):
    t = _type_of(node)
    if t != 'nodeset':
        raise QueryError('type error: expected a node-set, found %s' % t)


def _check_steps(steps):
    for step in steps:
        for pred in step[3]:
            _type_of(pred)


def _type_of(node):
    tag = node[0]
    if tag == 'num':
        return 'number'
    if tag == 'str':
        return 'string'
    if tag == 'neg':
        _type_of(node[1])
        return 'number'
    if tag == 'bin':
        _type_of(node[2])
        _type_of(node[3])
        return 'boolean' if node[1] in _BOOL_OPS else 'number'
    if tag == 'union':
        _require_nodeset(node[1])
        _require_nodeset(node[2])
        return 'nodeset'
    if tag == 'call':
        name, args = node[1], node[2]
        spec = FUNCTIONS.get(name)
        if spec is None:
            raise QueryError('unknown function: %s()' % name)
        lo, hi, result = spec
        if not lo <= len(args) <= hi:
            raise QueryError('wrong number of arguments for %s()' % name)
        for arg in args:
            _type_of(arg)
        if name == 'count':
            _require_nodeset(args[0])
        return result
    if tag == 'path':
        _check_steps(node[2])
        return 'nodeset'
    if tag == 'filter':
        _require_nodeset(node[1])
        for pred in node[2]:
            _type_of(pred)
        return 'nodeset'
    if tag == 'pathexpr':
        _require_nodeset(node[1])
        _check_steps(node[2])
        return 'nodeset'
    raise QueryError('internal error: unknown AST node %r' % (tag,))
