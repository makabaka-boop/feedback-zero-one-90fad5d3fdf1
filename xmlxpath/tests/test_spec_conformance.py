#!/usr/bin/env python3
"""Spec-conformance tests for points where libxml2 is known to deviate
from the XPath 1.0 recommendation (xpx follows the recommendation):

* number() accepts only the Number grammar of the recommendation: no
  exponent, no leading '+' (libxml2 uses strtod and accepts both);
* string(number) prints the shortest decimal that uniquely identifies
  the IEEE 754 value (libxml2 uses a fixed %.15g formatting).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xpx import service

XML = '<r><a/><a/></r>'
ALL = [{'path': [0], 'value': ''}, {'path': [1], 'value': ''}]
NONE = []

CASES = [
    # number(): exponent / plus sign are NaN per the recommendation
    ("/r/a[number('1e3')!=number('1e3')]", ALL),
    ("/r/a[number('1E3')!=number('1E3')]", ALL),
    ("/r/a[number('+3')!=number('+3')]", ALL),
    ("/r/a[number(' 3 ')=3]", ALL),
    ("/r/a[number('3.')=3]", ALL),
    ("/r/a[number('.5')=0.5]", ALL),
    ("/r/a[number('\t-3\n')=-3]", ALL),
    ("/r/a[number('3 5')!=number('3 5')]", ALL),
    # string(number): shortest uniquely-identifying decimal
    ("/r/a[string(1 div 3)='0.3333333333333333']", ALL),
    ("/r/a[string(2 div 3)='0.6666666666666666']", ALL),
    ("/r/a[string(0.1+0.2)='0.30000000000000004']", ALL),
    ("/r/a[string(1.5)='1.5']", ALL),
    ("/r/a[string(123456789)='123456789']", ALL),
    ("/r/a[string(0.000001)='0.000001']", ALL),
    ("/r/a[string(0.0000001)='0.0000001']", ALL),
    # the literal rounds to the nearest double: 12345678901234567168
    ("/r/a[string(12345678901234567890)='12345678901234567168']", ALL),
    ("/r/a[string(1 div 7)='0.14285714285714285']", ALL),
]

# The recommendation (section 5) orders the attribute nodes of an element
# before its children; hence the following axis of an attribute contains
# the owner element's children.  libxml2 skips them, so these cases are
# asserted here instead of in the lxml comparison.
XML2 = '<r><p/><a x="1"><b/><c/></a><d/></r>'
CASES2 = [
    ('//a[@x/following::*[1]=//a/b]', [{'path': [1], 'value': ''}]),
    ('//a[@x/following::*[2]=//a/c]', [{'path': [1], 'value': ''}]),
    ('//a[@x/following::*[last()]=//d]', [{'path': [1], 'value': ''}]),
    ('//a[count(@x/following::*)=3]', [{'path': [1], 'value': ''}]),
    ('//a[@x/preceding::*[1]=//p]', [{'path': [1], 'value': ''}]),
    ('//a[count(@x/preceding::*)=1]', [{'path': [1], 'value': ''}]),
    # attributes sort before the owner's children in document order
    ('//a[( @x | b )[1] = @x]', [{'path': [1], 'value': ''}]),
    ('//a[( @x | b )[last()] = b]', [{'path': [1], 'value': ''}]),
]


def main():
    failures = 0
    queries = [q for q, _ in CASES]
    results = service.run(XML, queries)
    for (q, expected), actual in zip(CASES, results):
        if actual != expected:
            failures += 1
            print('FAIL %r\n  want %r\n  got  %r' % (q, expected, actual))
    queries2 = [q for q, _ in CASES2]
    results2 = service.run(XML2, queries2)
    for (q, expected), actual in zip(CASES2, results2):
        if actual != expected:
            failures += 1
            print('FAIL %r\n  want %r\n  got  %r' % (q, expected, actual))
    total = len(CASES) + len(CASES2)
    print('spec conformance: %d cases, %d failures' % (total, failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
