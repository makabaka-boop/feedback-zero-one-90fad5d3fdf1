#!/usr/bin/env python3
"""Randomized differential test: xpx vs lxml.

Generates random XML documents (within the supported subset) and random
node-set-valued XPath queries, then compares the resulting element
lists.  Attribute-order-dependent queries (@* with positional
predicates) are never generated; attribute order is verified separately
in test_attr_order.py.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lxml import etree

from xpx import service
from compare_lxml import _document_context, _lxml_path

SEED = 20261113
ROUNDS = 400

NAMES = ['a', 'b', 'c', 'd']
ATTRS = ['x', 'y', 'n']
ATTR_VALUES = ['1', '2', '10', 'v', '']
TEXTS = ['t', '1', '  ', 'x y', '0']


def gen_xml(rng, depth=0):
    name = rng.choice(NAMES)
    attrs = ''.join(' %s="%s"' % (a, rng.choice(ATTR_VALUES))
                    for a in rng.sample(ATTRS, rng.randint(0, 2)))
    parts = []
    if depth < 3:
        for _ in range(rng.randint(0, 3)):
            kind = rng.random()
            if kind < 0.55:
                parts.append(gen_xml(rng, depth + 1))
            elif kind < 0.8:
                parts.append(rng.choice(TEXTS))
            elif kind < 0.9:
                parts.append('<![CDATA[%s]]>' % rng.choice(TEXTS))
            else:
                parts.append('&#x41;')
    if not parts:
        return '<%s%s/>' % (name, attrs)
    return '<%s%s>%s</%s>' % (name, attrs, ''.join(parts), name)


def gen_nodetest(rng):
    r = rng.random()
    if r < 0.45:
        return rng.choice(NAMES)
    if r < 0.7:
        return '*'
    if r < 0.85:
        return 'node()'
    return 'text()'


def gen_bool_expr(rng, depth):
    r = rng.random()
    if depth > 2 or r < 0.35:
        return gen_predicate_inner(rng)
    if r < 0.55:
        return '%s %s %s' % (gen_bool_expr(rng, depth + 1),
                             rng.choice(['and', 'or']),
                             gen_predicate_inner(rng))
    if r < 0.7:
        return 'not(%s)' % gen_predicate_inner(rng)
    if r < 0.85:
        return '%s %s %s' % (gen_arith(rng),
                             rng.choice(['=', '!=', '<', '<=', '>', '>=']),
                             gen_arith(rng))
    return '(%s)' % gen_bool_expr(rng, depth + 1)


def gen_arith(rng):
    r = rng.random()
    if r < 0.3:
        return str(rng.randint(0, 4))
    if r < 0.5:
        return rng.choice(['position()', 'last()'])
    if r < 0.65:
        return 'count(%s)' % rng.choice(NAMES + ['*', '@*'])
    if r < 0.8:
        return '@%s' % rng.choice(ATTRS)
    return '%s %s %s' % (gen_arith(rng), rng.choice(['+', '-', '*',
                                                     'div', 'mod']),
                         str(rng.randint(1, 3)))


def gen_predicate_inner(rng):
    r = rng.random()
    if r < 0.2:
        return '@%s' % rng.choice(ATTRS)
    if r < 0.35:
        return rng.choice(NAMES)
    if r < 0.5:
        return "%s='%s'" % (rng.choice(NAMES + ['@' + a for a in ATTRS]),
                            rng.choice(TEXTS + ATTR_VALUES))
    if r < 0.65:
        return 'not(%s)' % rng.choice(NAMES + ['@' + a for a in ATTRS])
    if r < 0.8:
        return 'string(.)%s'% rng.choice(["='t'", "!='x'"])
    return 'boolean(%s)' % rng.choice(NAMES)


def gen_predicate(rng, depth):
    inner = gen_bool_expr(rng, 0) if rng.random() < 0.5 \
        else gen_predicate_simple(rng)
    return '[%s]' % inner


def gen_predicate_simple(rng):
    r = rng.random()
    if r < 0.15:
        return '%d' % rng.randint(0, 3)
    if r < 0.25:
        return 'last()'
    if r < 0.4:
        return 'position()%s%d' % (rng.choice(['=', '!=', '<', '<=',
                                               '>', '>=']),
                                   rng.randint(1, 3))
    if r < 0.5:
        return '@%s' % rng.choice(ATTRS)
    if r < 0.6:
        return "@%s='%s'" % (rng.choice(ATTRS), rng.choice(ATTR_VALUES))
    if r < 0.7:
        return '%s' % rng.choice(NAMES)
    if r < 0.78:
        return 'not(@%s)' % rng.choice(ATTRS)
    if r < 0.86:
        return 'count(%s)%s%d' % (rng.choice(NAMES + ['*', '@*']),
                                  rng.choice(['=', '<', '>']),
                                  rng.randint(0, 3))
    if r < 0.93:
        return "%s='%s'" % (rng.choice(NAMES), rng.choice(TEXTS))
    return '.=%s' % rng.choice(["'t'", '1', "''"])


AXES = ['child', 'descendant', 'self', 'parent', 'attribute',
        'following-sibling', 'preceding-sibling', 'ancestor',
        'ancestor-or-self', 'descendant-or-self', 'following', 'preceding']


def gen_step(rng, depth):
    r = rng.random()
    if r < 0.08:
        step = '.'
    elif r < 0.14:
        step = '..'
    elif r < 0.2:
        step = '@' + (rng.choice(ATTRS) if rng.random() < 0.7 else '*')
    elif r < 0.35:
        step = '%s::%s' % (rng.choice(AXES), gen_nodetest(rng))
    else:
        step = gen_nodetest(rng)
    for _ in range(rng.randint(0, 1 if depth > 1 else 2)):
        step += gen_predicate(rng, depth)
    return step


def gen_query(rng):
    def path(depth):
        n = rng.randint(1, 3)
        q = gen_step(rng, depth)
        for _ in range(n - 1):
            q += rng.choice(['/', '//']) + gen_step(rng, depth + 1)
        return q

    r = rng.random()
    if r < 0.45:
        q = rng.choice(['/', '//']) + path(0)
    elif r < 0.6:
        q = path(0)
    elif r < 0.75:
        q = '(%s%s)[%s]' % (rng.choice(['/', '//']), path(0),
                            rng.choice(['1', 'last()', '2']))
    elif r < 0.9:
        q = '%s%s | %s%s' % (rng.choice(['/', '//']), path(0),
                             rng.choice(['/', '//']), path(0))
    else:
        q = '(%s%s)/%s' % (rng.choice(['/', '//']), path(0),
                           gen_step(rng, 1))
    return q


def lxml_results(xml_str, query):
    root = etree.fromstring(xml_str.encode('utf-8'))
    raw = root.getroottree().xpath(_document_context(query))
    return [
        {'path': _lxml_path(e), 'value': ''.join(e.itertext())}
        for e in raw if isinstance(e, etree._Element)
    ]


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else SEED
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else ROUNDS
    rng = random.Random(seed)
    failures = 0
    total = 0
    for i in range(rounds):
        xml = '<r>%s</r>' % ''.join(gen_xml(rng)
                                    for _ in range(rng.randint(1, 3)))
        try:
            service.run(xml, [])
        except Exception:
            print('generator produced XML rejected by xpx: %r' % xml)
            failures += 1
            continue
        for _ in range(6):
            query = gen_query(rng)
            total += 1
            try:
                expected = lxml_results(xml, query)
            except etree.XPathError:
                continue        # generated query outside lxml's grammar?
            try:
                actual = service.run(xml, [query])[0]
            except Exception as exc:
                failures += 1
                print('XPX REJECTED/FAILED')
                print('  xml:   %r' % xml)
                print('  query: %r' % query)
                print('  error: %r' % (exc,))
                continue
            if expected != actual:
                failures += 1
                print('MISMATCH')
                print('  xml:   %r' % xml)
                print('  query: %r' % query)
                print('  lxml:  %r' % (expected,))
                print('  xpx:   %r' % (actual,))
        if failures > 10:
            break
    print('random differential: %d queries, %d failures' % (total, failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
