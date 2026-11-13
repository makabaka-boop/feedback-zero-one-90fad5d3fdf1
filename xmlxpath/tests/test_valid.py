#!/usr/bin/env python3
"""Acceptance tests: valid inputs that must succeed."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xpx import service

CASES = [
    # (xml, queries, expected_results)
    ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><r/>',
     ['/r'], [[{'path': [], 'value': ''}]]),
    ("<?xml version='1.0' encoding='utf-8'?><r/>",
     ['/r'], [[{'path': [], 'value': ''}]]),
    ('<?xml version="1.0"?><r/>', ['/r'], [[{'path': [], 'value': ''}]]),
    ('﻿<r/>', ['/r'], [[{'path': [], 'value': ''}]]),
    ('<r>a<![CDATA[b]]>c</r>', ['/r', '/r/text()', '/r/count(text())' if False else '/r[text()]'],
     [[{'path': [], 'value': 'abc'}], [], [{'path': [], 'value': 'abc'}]]),
    ('<r>&#72;&#x69;</r>', ['/r'], [[{'path': [], 'value': 'Hi'}]]),
    ('<r>&lt;&gt;&amp;&quot;&apos;</r>', ['/r'],
     [[{'path': [], 'value': "<>&\"'"}]]),
    ('<r a="&lt;&#x41;&amp;"/>', ['/r[@a="<A&"]'],
     [[{'path': [], 'value': ''}]]),
    ('<r>a<b>c</b>d<e>f</e>g</r>', ['/r'],
     [[{'path': [], 'value': 'acdfg'}]]),
    ('<r><café ö="1">☃</café></r>', ['/r/café', '/r/café[@ö="1"]'],
     [[{'path': [0], 'value': '☃'}], [{'path': [0], 'value': '☃'}]]),
    ('<r>😀</r>', ['/r'], [[{'path': [], 'value': '😀'}]]),
    ('<r/>', [], []),
    ('<r><a/></r>', ['/r/a/text()', '/r/a/@*', '/', '//comment()',
                     '//processing-instruction()', '/r/..', '/..'],
     [[], [], [], [], [], [], []]),
    ('<r><a/><b/><c/></r>', ['/r/c/preceding::*[1]'],
     [[{'path': [1], 'value': ''}]]),
    ('<r><a/><b/><c/></r>', ['(/r/*)[last()]', '/r/*[last()]'],
     [[{'path': [2], 'value': ''}], [{'path': [2], 'value': ''}]]),
    ('<r><a x="1"/></r>', ['child::r', 'r', './r', 'child::r/child::a'],
     [[{'path': [], 'value': ''}], [{'path': [], 'value': ''}],
      [{'path': [], 'value': ''}], [{'path': [0], 'value': ''}]]),
    ('<r><a><b>deep</b></a></r>',
     ['//b/ancestor::*', '//b/ancestor-or-self::*'],
     [[{'path': [], 'value': 'deep'}, {'path': [0], 'value': 'deep'}],
      [{'path': [], 'value': 'deep'}, {'path': [0], 'value': 'deep'},
       {'path': [0, 0], 'value': 'deep'}]]),
    # whitespace preserved
    ('<r>  <a> x </a>  </r>', ['/r', '/r/a'],
     [[{'path': [], 'value': '   x   '}], [{'path': [0], 'value': ' x '}]]),
    # attribute value normalization (literal tab/newline -> space)
    ('<r a="x\ty\nz"/>', ['/r[@a="x y z"]'], [[{'path': [], 'value': ''}]]),
    # but character references are NOT normalized
    ('<r a="x&#9;y"/>', ['/r[@a="x\ty"]'], [[{'path': [], 'value': ''}]]),
]


def main():
    failures = 0
    for xml, queries, expected in CASES:
        try:
            actual = service.run(xml, queries)
        except Exception as exc:
            failures += 1
            print('FAIL %r\n  raised %r' % (xml[:60], exc))
            continue
        if actual != expected:
            failures += 1
            print('FAIL %r\n  want %r\n  got  %r' % (xml[:60], expected, actual))
    # a valid surrogate pair inside the JSON text must reach the XML layer
    raw = '{"xml": "<r>\\ud83d\\ude00</r>", "queries": ["/r"]}'
    results = service.run_json_text(raw)
    if results != [[{'path': [], 'value': '\U0001f600'}]]:
        failures += 1
        print('FAIL surrogate pair: %r' % (results,))
    print('acceptance: %d cases, %d failures' % (len(CASES) + 1, failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
