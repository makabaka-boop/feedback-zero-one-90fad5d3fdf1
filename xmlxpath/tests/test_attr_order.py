#!/usr/bin/env python3
"""Attribute order verification (independent of lxml).

The specification requires the attributes of an element to be ordered by
name in Unicode code point order.  This defines their document order and
hence the behaviour of positional predicates on the attribute axis.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xpx import service

# code point order: A(0x41) < B(0x42) < a(0x61) < z(0x7A) < é(0xE9)
XML = '<r><e z="1" a="2" m="3"/><e B="4" A="5" a="6"/><e é="7" z="8"/></r>'

CASES = [
    # first <e>: attributes sorted a,m,z
    ('/r/e[1][@*[1]="2"]', [[0]]),       # @*[1] = a
    ('/r/e[1][@*[2]="3"]', [[0]]),       # @*[2] = m
    ('/r/e[1][@*[3]="1"]', [[0]]),       # @*[3] = z
    ('/r/e[1][@*[last()]="1"]', [[0]]),
    ('/r/e[1][@*[1]="1"]', []),          # document order would give z first
    # second <e>: code points A(65) < B(66) < a(97)
    ('/r/e[2][@*[1]="5"]', [[1]]),       # @*[1] = A
    ('/r/e[2][@*[2]="4"]', [[1]]),       # @*[2] = B
    ('/r/e[2][@*[3]="6"]', [[1]]),       # @*[3] = a
    ('/r/e[2][@*[1]="4"]', []),
    # third <e>: z(0x7A) < é(0xE9)
    ('/r/e[3][@*[1]="8"]', [[2]]),       # @*[1] = z
    ('/r/e[3][@*[2]="7"]', [[2]]),       # @*[2] = é
    ('/r/e[3][@*[last()]="7"]', [[2]]),
    # string()/number() take the first attribute in (sorted) document order
    ('/r/e[1][string(@*)="2"]', [[0]]),
    ('/r/e[2][string(@*)="5"]', [[1]]),
    ('/r/e[3][string(@*)="8"]', [[2]]),
    # count is order-independent
    ('/r/e[count(@*)=3]', [[0], [1]]),
    ('/r/e[count(@*)=2]', [[2]]),
    # attribute axis of a step result, positional across the axis
    ('/r/e[1]/attribute::*[1][.="2"]', []),   # attribute result -> filtered
]


def main():
    failures = 0
    queries = [q for q, _ in CASES]
    results = service.run(XML, queries)
    for (q, expected), actual in zip(CASES, results):
        paths = [item['path'] for item in actual]
        if paths != expected:
            failures += 1
            print('FAIL %r: expected paths %r, got %r' % (q, expected, paths))
    # the attribute-only query must yield an empty element list
    if results[-1] != []:
        failures += 1
        print('FAIL: attribute result not filtered to elements')
    print('attribute order: %d cases, %d failures' % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
