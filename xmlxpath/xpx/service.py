"""Top-level request handling: validate the input object, run the queries."""

from . import checker, evaluator, jsonstrict, parser, xmlmodel
from .errors import QueryError, Reject
from .jsonstrict import keypath


def validate_input(data):
    """Check the decoded JSON object; return ``(xml, queries)``."""
    if not isinstance(data, dict):
        raise Reject('$', 'top-level value must be an object')
    for key in data:
        if key not in ('xml', 'queries'):
            raise Reject(keypath('$', key), 'unknown member')
    if 'xml' not in data:
        raise Reject('$.xml', 'missing member')
    if 'queries' not in data:
        raise Reject('$.queries', 'missing member')
    xml = data['xml']
    if not isinstance(xml, str):
        raise Reject('$.xml', 'member must be a string')
    queries = data['queries']
    if not isinstance(queries, list):
        raise Reject('$.queries', 'member must be an array')
    for i, q in enumerate(queries):
        if not isinstance(q, str):
            raise Reject('$.queries[%d]' % i, 'query must be a string')
    return xml, queries


def run(xml, queries):
    """Evaluate *queries* against *xml*; return the results array."""
    doc = xmlmodel.parse(xml)

    # 1. validate the full syntax and subset of every query first
    asts = []
    for i, q in enumerate(queries):
        try:
            ast = parser.parse(q)
            checker.check(ast)
        except QueryError as exc:
            raise Reject('$.queries[%d]' % i, str(exc))
        except RecursionError:
            raise Reject('$.queries[%d]' % i, 'expression too deeply nested')
        asts.append(ast)

    # 2. evaluate (with standard short-circuiting) and shape the output
    results = []
    for i, ast in enumerate(asts):
        try:
            value = evaluator.evaluate(ast, doc)
        except QueryError as exc:
            raise Reject('$.queries[%d]' % i, str(exc))
        except RecursionError:
            raise Reject('$.queries[%d]' % i, 'expression too deeply nested')
        if not isinstance(value, list):
            raise Reject('$.queries[%d]' % i,
                         'type error: result is not a node-set')
        elements = _unique_elements(value)
        results.append([
            {'path': xmlmodel.path_of(el), 'value': xmlmodel.string_value(el)}
            for el in elements
        ])
    return results


def _unique_elements(nodes):
    """Element-only node-set, deduplicated, in document order."""
    seen = {}
    for n in nodes:
        if isinstance(n, xmlmodel.Element):
            seen[id(n)] = n
    return sorted(seen.values(), key=lambda n: n.sort_key)


def run_json_text(text):
    """Convenience wrapper: raw JSON text in, results array out."""
    data = jsonstrict.loads(text)
    xml, queries = validate_input(data)
    return run(xml, queries)
