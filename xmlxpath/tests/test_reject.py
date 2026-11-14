#!/usr/bin/env python3
"""Rejection tests: illegal inputs must reject the whole request and
report the correct field path ($, $.xml, $.queries[i], member paths)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xpx import jsonstrict, service
from xpx.errors import Reject

GOOD_XML = '<r><a/><b/><c/></r>'
GOOD_QUERY = '/r/c/preceding::*[1]'


def check(raw, expected_path):
    """raw: bytes of the JSON input.  Returns (ok, detail)."""
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        # main.py maps this to '$'
        return (expected_path == '$', 'decode error -> $')
    try:
        data = jsonstrict.loads(text)
        xml, queries, merge = service.validate_input(data)
        service.run(xml, queries, merge)
    except Reject as exc:
        return (exc.path == expected_path,
                'path %r (want %r): %s' % (exc.path, expected_path, exc.message))
    return (False, 'input was ACCEPTED but must be rejected')


def J(obj):
    return json.dumps(obj, ensure_ascii=False).encode('utf-8')


CASES = []
for raw, path in [
    # -- JSON syntax errors -> $
    (b'', '$'),
    (b'{', '$'),
    (b'{"xml":1,}', '$'),
    (b'[1,2]', '$'),
    (b'"s"', '$'),
    (b'123', '$'),
    (b'null', '$'),
    (b'true', '$'),
    (b'{"xml":"<r/>","queries":[]} trailing', '$'),
    (b'{"xml":"<r/>","queries":[],}', '$'),
    (b"{'xml':1}", '$'),
    (b'{"xml":"<r/>","queries":[]', '$'),
    (b'\xef\xbb\xbf{"xml":1}', '$'),                 # BOM not allowed
    (b'{"xml":"<r/>","queries":["/r",]}', '$'),
    (b'{"xml":"<r/>","queries":[01]}', '$'),
    (b'{"xml":"<r/>","queries":[1e]}', '$'),
    (b'{"xml":"<r/>","queries":["a\x01b"]}', '$'),   # raw control char
    (b'{"xml":"<r/>","queries":["\\x"]}', '$'),      # bad escape
    (b'{"xml":"<r/>","queries":["abc]}', '$'),       # unterminated string
    (b'\xff\xfe{"xml":1}', '$'),                     # not UTF-8
    (b'{"xml":"<r/\xc3\x28>","queries":[]}', '$'),   # invalid UTF-8
    (b'{"xml":"<r/>","queries":[NaN]}', '$'),
    (b'{"xml":"<r/>","queries":[Infinity]}', '$'),
    (b'{"xml":"<r/>","queries":[+1]}', '$'),
    (b'{"xml":"<r/>","queries":[.5]}', '$'),
    # -- duplicate / unknown / mistyped members
    (b'{"xml":"<r/>","xml":"<r/>","queries":[]}', '$.xml'),
    (b'{"xml":"<r/>","queries":[],"queries":[]}', '$.queries'),
    (b'{"xml":"<r/>","queries":[],"extra":1}', '$.extra'),
    (b'{"xml":"<r/>","queries":[],"XML":""}', '$.XML'),
    (b'{"queries":[]}', '$.xml'),
    (b'{"xml":"<r/>"}', '$.queries'),
    (b'{}', '$.xml'),
    (b'{"xml":1,"queries":[]}', '$.xml'),
    (b'{"xml":["<r/>"],"queries":[]}', '$.xml'),
    (b'{"xml":null,"queries":[]}', '$.xml'),
    (b'{"xml":"<r/>","queries":"/r"}', '$.queries'),
    (b'{"xml":"<r/>","queries":{}}', '$.queries'),
    (b'{"xml":"<r/>","queries":[1]}', '$.queries[0]'),
    (b'{"xml":"<r/>","queries":[null]}', '$.queries[0]'),
    (b'{"xml":"<r/>","queries":[["/r"]]}', '$.queries[0]'),
    (b'{"xml":"<r/>","queries":["/r",2]}', '$.queries[1]'),
    # -- merge member schema
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":1}', '$.merge'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":[]}', '$.merge'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":null}', '$.merge'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":"x"}', '$.merge'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":{}}', '$.merge.base'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":{"other":"<r id=\'r\'/>"}}',
     '$.merge.base'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":{"base":"<r id=\'r\'/>"}}',
     '$.merge.other'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":{"base":1,"other":"<r id=\'r\'/>"}}',
     '$.merge.base'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":{"base":"<r id=\'r\'/>","other":2}}',
     '$.merge.other'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":'
     b'{"base":"<r id=\'r\'/>","other":"<r id=\'r\'/>","extra":1}}',
     '$.merge.extra'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":'
     b'{"base":"<r id=\'r\'/>","other":"<r id=\'r\'/>","base":"<r id=\'r\'/>"}}',
     '$.merge.base'),
    (b'{"xml":"<r id=\'r\'/>","queries":[],"merge":{"base":"<r id=\'r\'/>",'
     b'"other":"<r id=\'r\'/>"},"merge":{"base":"<r id=\'r\'/>","other":"<r id=\'r\'/>"}}',
     '$.merge'),
    # -- lone surrogates
    (b'{"xml":"<r/>","queries":["\\ud800"]}', '$.queries[0]'),
    (b'{"xml":"<r/>","queries":["\\udfff"]}', '$.queries[0]'),
    (b'{"xml":"<r/>","queries":["\\ud800x"]}', '$.queries[0]'),
    (b'{"xml":"<r/>","queries":["\\ud800\\u0041"]}', '$.queries[0]'),
    (b'{"xml":"\\ud800","queries":[]}', '$.xml'),
    (b'{"xml":"<r/>","queries":["\\udc00\\ud800"]}', '$.queries[0]'),
    (b'{"\\ud800":1,"xml":"<r/>","queries":[]}', '$'),
]:
    CASES.append((raw, path))

# valid surrogate PAIR must be accepted (not a rejection case) -- checked
# separately below.

# -- XML errors -> $.xml
for xml in [
    '', ' ', '<r>', '<r></s>', '<r/><r/>', 'text', '<r/><!--x-->',
    '<!DOCTYPE r><r/>',
    '<!DOCTYPE r [<!ENTITY e "x">]><r>&e;</r>',
    '<!DOCTYPE r SYSTEM "http://x/y"><r/>',
    '<r><!-- comment --></r>',
    '<r><?pi data?></r>',
    '<?pi data?><r/>',
    '<r xmlns="urn:x"/>',
    '<r xmlns:a="urn:x"/>',
    '<a:r/>',
    '<r a:b="1"/>',
    '<r><a:b/></r>',
    '<r>&undefined;</r>',
    '<r>&#xD800;</r>',
    '<r>&#xFFFE;</r>',
    '<r>&#0;</r>',
    '<r>\x01</r>',
    '<?xml version="1.1"?><r/>',
    '<?xml version="1.0" encoding="ISO-8859-1"?><r/>',
    '<?xml version="1.0" encoding="UTF-16"?><r/>',
    '<?xml version="1.0" encoding="utf-16"?><r/>',
    '<r a="1" a="2"/>',
    '<r><a></r>',
    '<r/>junk',
    '<?xml version="1.0"?><?xml version="1.0"?><r/>',
    '<r a="1" a="1"/>',
    '<r>&#xD7FF;&#xE000;</r>'.replace('&#xD7FF;', '\ud7ff').replace('&#xE000;', '\ue000') if False else '<r>\x00</r>',
    '<r\t/>x',
]:
    CASES.append((J({'xml': xml, 'queries': [GOOD_QUERY]}), '$.xml'))

# -- query errors -> $.queries[i]
for q in [
    '', '   ', '/r[', '/r]', '(', ')', '(/', '()', '(//a', '//a)',
    '$x', '$', '//a[$x=1]', '/a:b', '/a:b/c', '/r/a:b', '/r/@a:b',
    '//namespace::*', '/r/namespace::a', '/r/foo::a',
    '/r/@', '/r/attribute::', '/r//', '//', '/r/', '/r[1',
    '/r/node(1)', '/r/comment(1)', "/r/processing-instruction('a','b')",
    '/r/string-length()', '/r/name()', '/r/concat()', '/r/true()',
    '/r/false()', '/r/normalize-space()', '/r/starts-with()',
    '/r[position(1)]', '/r[last(1)]', '/r[count()]', '/r[count(1,2)]',
    '/r[string(1,2)]', '/r[boolean()]', '/r[boolean(1,2)]', '/r[not()]',
    '/r[not(1,2)]', '/r[number(1,2)]', '/r[id("x")]',
    '1 | /r', '/r | 1', "'a' | /r", 'count(1)', 'count("x")',
    'count(//a) | 1', '1/2', "'a'/b", '1//a', 'true()/a', 'count(/r)/a',
    '(1)/a', '("x")[1]', '(1)[position()=1]', '1[2]', "'s'[1]",
    '1+1', '1', "'string'", 'count(/r)', 'string(/r)', 'boolean(/r)',
    'not(/r)', 'number(/r)', 'position()', 'last()', '1=1', '/r=1',
    '/r[position()=1]=/r', 'not(/r)=not(/r)', '/r | /r=1',
    '/r/child::node()/parent::text()',  # fine actually -- NOT here
]:
    if q == '/r/child::node()/parent::text()':
        continue
    CASES.append((J({'xml': GOOD_XML, 'queries': [q]}), '$.queries[0]'))

# error in the second query -> $.queries[1]; whole run rejected
CASES.append((J({'xml': GOOD_XML, 'queries': [GOOD_QUERY, '$v']}),
              '$.queries[1]'))
CASES.append((J({'xml': GOOD_XML, 'queries': [GOOD_QUERY, '/r', '1+1']}),
              '$.queries[2]'))
# both XML and a query are broken: either path is acceptable -> use a
# marker; we require $.xml here because XML is validated first
CASES.append((J({'xml': '<r>', 'queries': ['$v']}), '$.xml'))


def main():
    failures = 0
    for raw, path in CASES:
        ok, detail = check(raw, path)
        if not ok:
            failures += 1
            print('FAIL %r\n     %s' % (raw[:90], detail))
    print('rejection: %d cases, %d failures' % (len(CASES), failures))

    # a valid surrogate pair (U+1D600) inside a query string is legal JSON;
    # the query itself is then rejected as an XPath syntax error, not as a
    # lone-surrogate error
    try:
        data = jsonstrict.loads(
            '{"xml":"<r/>","queries":["\\ud835\\ude00"]}')
        q = data['queries'][0]
        if q != '\U0001d600':
            print('FAIL: surrogate pair decoded incorrectly: %r' % q)
            failures += 1
    except Reject as exc:
        print('FAIL: valid surrogate pair rejected: %r' % (exc,))
        failures += 1
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
