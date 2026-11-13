#!/usr/bin/env python3
"""Differential test: compare xpx against lxml on the legal intersection.

For every (document, query) pair both engines are run; the resulting
element lists (path + value) must be identical.  Queries that depend on
attribute *order* are excluded here (lxml keeps document order, xpx sorts
by code point) and are covered by test_attr_order.py instead.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lxml import etree

from xpx import service

XML_DOCS = [
    '<r><a/><b/><c/></r>',
    '<r><a x="1" y="2"><b>text</b></a><a x="2"><b/><b>more</b></a><c/></r>',
    '<r> t1 <a> t2 <b> t3 </b> t4 </a> t5 </r>',
    '<r><a><![CDATA[cdata & <>]]></a><b>&lt;&amp;&gt;&#65;&#x42;</b></r>',
    '<r><a n="10"/><a n="3"/><a/></r>',
    '<deep><a><a><a><a/></a></a></a></deep>',
    '<r><x><y/><y/></x><x><y/></x></r>',
    '<r><a><b><c>deep</c></b></a><a><c>other</c></a></r>',
    '<r><a/><a/><a/><a/><a/></r>',
    '<?xml version="1.0" encoding="UTF-8"?><r><a>1</a><a>2</a></r>',
    '<r><café>☃</café><a/></r>',
    '<r><a b=" "><c/><d>  <e> x </e>  </d></a></r>',
    '<r><a><b/></a><b/><a><b><b/></b></a></r>',
    '<r>\n  <a n="1">one</a>\n  <a n="2">two</a>\n</r>',
    '<r><a/><b><c/><c/><c/></b><d><c/></d></r>',
]

QUERIES = [
    # absolute / relative basics
    '/r', 'r', '/r/*', '/r/a', '/r/a/b', '/r/a/c', '/deep/a/a/a',
    '/', '.', './r', '/r/.', '/r/a/..', '/r/a/b/../..', '/r/a/b/c/../../..',
    # descendant shortcuts
    '//a', '//a/b', '/r//b', '//a//b', '//b//c', '//a/b/c',
    # node tests
    '//node()', '/r/node()', '//text()', '/r/text()', '//comment()',
    '//processing-instruction()', "//processing-instruction('x')",
    '//*', '//a/node()', '//a/text()', '/node()',
    # positional predicates
    '/r/a[1]', '/r/a[2]', '/r/a[0]', '/r/a[-1]', '/r/a[last()]',
    '/r/a[position()=2]', '/r/a[position()!=1]', '/r/a[position()<3]',
    '/r/a[position()<=2]', '/r/a[position()>1]', '/r/a[position()>=2]',
    '/r/a[position()=last()]', '/r/a[1][1]', '/r/a[1][last()]',
    '/r/a[2][1]', '//a[1]', '(//a)[1]', '(//a)[2]', '(//a)[last()]',
    '(//a)[position()=2]', '//a[.5]', '/r/a[1.0]',
    '//a[1 div 0]', '//a[-1 div 0]', '//a[0 div 0]',
    # attribute predicates (no attribute-order dependency)
    '//a[@x]', '//a[not(@x)]', "//a[@x='1']", "//a[@x!='1']",
    '//a[@x and @y]', '//a[count(@*)=2]', '//a[count(@*)>0]',
    '//a[count(@*)<1]', '//a[@*]', '//@*', '//@x',
    # axes (explicit)
    '//c/ancestor::*', '//c/ancestor-or-self::*', '//c/ancestor-or-self::node()',
    '//b/descendant::*', '//b/descendant-or-self::*', '/descendant::a',
    '/descendant-or-self::node()', '//c/following::*', '//c/following::node()',
    '//c/preceding::*', '//c/preceding::node()', '//c/preceding::*[1]',
    '//c/preceding::*[last()]', '//c/following::*[1]', '//c/following::*[last()]',
    '//a/following-sibling::*', '//a/following-sibling::*[1]',
    '//a/preceding-sibling::*', '//a/preceding-sibling::*[1]',
    '//a/preceding-sibling::*[last()]', '//c/self::*', '//c/parent::*',
    '//c/parent::node()', '//b/ancestor::*[1]', '//b/ancestor::*[last()]',
    'child::r', 'child::r/child::a', '/child::*', '//a/child::*',
    '//a/attribute::*', '//a/self::node()', '//a/parent::node()',
    # union
    '//a | //b', '//a | //a', '//a | //b | //c', '/r/a | /r/a[1]',
    '(//a | //b)[1]', '(//a | //c)[last()]', '//a[1] | //a[2]',
    '//x/y | //y', '(//a | //b)/c',
    # boolean / comparison predicates
    '//a[b]', '//a[not(b)]', '//a[b and @x]', '//a[b or c]',
    "//a[b='text']", "//a[b!='text']", "//a[.='text']", "//a[.!='x']",
    '//a[*]', '//a[*="deep"]', '//a[boolean(b)]', '//a[boolean(@x)]',
    "//a[string(.)='text']", "//a[string(b)='text']",
    '//a[number(@n)>5]', '//a[number(@n)>=3]', '//a[number(@n)<4]',
    '//a[number(@n)=10]', '//a[number(@n)!=10]', '//a[number(.)=1]',
    '//a[@n+1=4]', '//a[@n-1=9]', '//a[@n*2=20]', '//a[@n div 2=5]',
    '//a[@n mod 3=1]', '//a[-@n=-10]', '//a[1+1=2]', '//a[2*3=6]',
    '//a[5 div 2=2.5]', '//a[5 mod 2=1]', '//a[1<2]', '//a[2<=1]',
    "//a['x'='x']", "//a['x'!='y']", "//a['x'<'y']",
    '//a[true]', '//a[false]', '//a[0]', '//a[""]',
    '//a[count(b)=2]', '//a[count(*)>0]', '//a[count(c)=3]',
    '//a[position() mod 2 = 0]', '//a[position() div 2 < 1]',
    '//a[position() - 1 = 0]', '//a[position() + 1 = 2]',
    '//a[not(position()=1)]', '//a[not(position()=last())]',
    '//a[b][1]', '//a[1][b]', '//a[b][c]', '//a[b][@n]',
    # string / number / boolean functions inside predicates
    "//a[string(@x)='1']", "//a[string(.)='']", '//a[string()=string()]',
    '//a[number()=number()]', '//a[boolean(0)=boolean(1)]',
    '//a[not(0)]', '//a[not(1)]', "//a[not('')]", "//a[not('x')]",
    # filter expressions with parentheses
    '(//a)', '((//a))', '(//a[1])', '(/r/a)[1]', '(/r/a)[last()]',
    '(//a)/b', '(//a)[1]/b', '(//a | //b)[1]/..', '(/r/*)[2]',
    '(//*)[position()=3]',
    # names that collide with operator keywords
    '/and', '//and', '/r/and', '//div', '//mod', '//or',
    # text-node relative paths inside predicates
    '//a[text()]', "//a[text()='text']", "//a[text()=' t2 ']",
    '//a[./b]', '//a[../@x]', '//b[../a]', '//a[/r/@n]',
    # whitespace tolerance and both literal styles
    '/r/a[ 1 ]', ' /r/a ', '//a[ @x = "1" ]', '//a[@x="1"]',
    "//a[@x='1' and position()=1]",
    # deep nesting / repeated names
    '//a/a', '//a//a', '/deep//a//a', '//a[a]', '//a[a[a]]',
    '//x/y[1]', '//x[1]/y[2]', '(//x/y)[1]', '(//x/y)[last()]',
    # attribute node as context (paths starting at an attribute)
    '//a[@x/..]', '//a[@x/../@y]', '//a[@x/ancestor::*]',
    '//a[@x/ancestor-or-self::node()]', '//a[@x/self::node()]',
    '//a[@x/descendant-or-self::node()]', '//a[@x/following-sibling::*]',
    '//a[@x/preceding-sibling::*]', '//a[@x/child::*]', '//a[@x/@*]',
    '//a[@x/preceding::*]', '//a[@x/preceding::*[1]]',
    # NOTE: following:: from an attribute is tested in
    # test_spec_conformance.py (libxml2 deviates from the recommendation)
    '//a[@x/parent::*/@y]', '//a[count(@x/ancestor::*)>0]',
    # nested predicates
    '//a[b[c[1]]]', '//a[b[c[1]][2]]', '//a[b[c][d]]',
    '//a[b[1][c[2]]]', '//a[./b/..//c]', '//a[b[c=' + "'deep'" + ']]',
    # node-set comparisons
    '//a[b=c]', '//a[b!=c]', '//a[@x=@y]', '//a[@x!=@y]',
    '//a[b<c]', '//a[b<=c]', '//a[b>c]', '//a[b>=c]',
    '//a[b<3]', '//a[b>3]', "//a[b<'v']", "//a[b>'v']",
    '//a[@x=../@y]', '//a[../@x=@y]', '//a[.//b=//c]',
    # mixed-type comparisons
    "//a['1'=1]", "//a['1'!=2]", "//a[boolean(1)=1]", "//a[boolean(0)='']",
    "//a[boolean(0)=0]", "//a[0=boolean(0)]", "//a[''!=0]",
    '//a[.<2]', '//a[.>2]', '//a[./@x=1]',
    # IEEE 754 arithmetic and number formatting
    '//a[5 div 0 = 1 div 0]', '//a[-5 div 0 = -1 div 0]',
    '//a[0 div 0 != 0 div 0]', '//a[not(0 div 0)]',
    '//a[5 mod 2 = 1]', '//a[-5 mod 3 = -2]', '//a[5 mod -3 = 2]',
    '//a[5 mod 0 != 5 mod 0]', '//a[2.5 mod 2 = 0.5]',
    "//a[string(0 div 0)='NaN']", "//a[string(1 div 0)='Infinity']",
    "//a[string(-1 div 0)='-Infinity']", "//a[string(2.5)='2.5']",
    "//a[string(-2.5)='-2.5']", "//a[string(0)='0']",
    "//a[string(1000000)='1000000']", "//a[string(0.1)='0.1']",
    "//a[string(1 div 4)='0.25']", "//a[string(-0.0)='0']",
    # string->number edge cases
    "//a[number(' 3 ')=3]", "//a[number('3.')=3]", "//a[number('.5')=0.5]",
    "//a[number('-3')=-3]", "//a[number('+3')!=number('+3')]",
    "//a[number('')!=number('')]",
    "//a[number('  ')!=number('  ')]", "//a[number('3.5.6')!=number('3.5.6')]",
    "//a[number('-')!=number('-')]",
    # boolean conversions
    "//a[boolean('')=boolean(0)]", "//a[boolean('x')=boolean(1)]",
    "//a[boolean(//zzz)=boolean('')]", "//a[not(//zzz)]",
    '//a[not(count(//zzz))]',
    # position/last in filter expressions
    '(//*)[position()=last()]', '(//a|//b)[position()<3]',
    '(//a|//b)[position()>2]', '(//a[1]|//b[1])[1]',
    '(//a)[1][1]', '(//a)[last()][1]', '(//a)[2][last()]',
    # string() of node-sets picks the first in document order
    '//a[string(b|c)=string(b)]', '//a[string(//b)=string((//b)[1])]',
    '//a[string(.)=string(./node())]',
    # miscellaneous tricky grammar
    '/r/a[1]/b[1]', '//a[1]//b[1]', '//a//b[1]/..',
    '/r//a//b', '//a/.//b', '//a/./b', '//a/..//b',
    '//a [ 1 ]', '//a[@x][1]', '//a[1][@x]', '//a[*][1]',
    '//a[child::b]', '//a[child::b="text"]', '//a[descendant::c]',
    '//a[self::a]', '//a[self::b]', '//a[parent::r]', '//a[parent::x]',
    '//a[./@n]', '//a[./@x=1]',
    # unions and filter chains inside predicates
    '//a[b | c]', '//a[(b | c)[1]]', '//a[(b | c)[last()]]',
    '//a[count(b | c)=2]', '//a[count(b | c)>1]', '//a[@x | @y]',
    '//a[(b)[1]]', '//a[(b)[1]/c]', '//a[(b|c)[1]/..]',
    '//a[b[position()=1]]', '//a[b[position()=last()]]',
    '//a[b[c[position()=last()]]]', '//a[b[1][c[1]]]',
    '(//a)[1]//b', '(//a)[last()]//b', '(//a[1])[1]',
    '/descendant-or-self::*', '//b/descendant-or-self::*',
    '//a/descendant-or-self::*', '//a/ancestor-or-self::*[1]',
    '//a/ancestor-or-self::*[last()]',
]


def lxml_results(xml_str, queries):
    parser = etree.XMLParser()
    root = etree.fromstring(xml_str.encode('utf-8'), parser)
    tree = root.getroottree()
    out = []
    for q in queries:
        raw = tree.xpath(_document_context(q))
        elems = [e for e in raw if isinstance(e, etree._Element)]
        out.append([
            {'path': _lxml_path(e), 'value': ''.join(e.itertext())}
            for e in elems
        ])
    return out


def _document_context(q):
    """lxml's ElementTree.xpath uses the root *element* as initial context
    node, while the specification (and xpx) uses the document node.  For a
    relative location path, prefixing '/./' forces the document context."""
    stripped = q.lstrip()
    if stripped and stripped[0] not in '/(':
        return '/./' + q
    return q


def _lxml_path(elem):
    parts = []
    node = elem
    while node.getparent() is not None:
        parent = node.getparent()
        # all children are elements (no comments/PIs in the corpus)
        parts.append(parent.index(node))
        node = parent
    parts.reverse()
    return parts


def main():
    failures = 0
    total = 0
    for xml in XML_DOCS:
        expected = lxml_results(xml, QUERIES)
        actual = service.run(xml, QUERIES)
        for q, exp, act in zip(QUERIES, expected, actual):
            total += 1
            if exp != act:
                failures += 1
                print('MISMATCH')
                print('  xml:   %r' % xml)
                print('  query: %r' % q)
                print('  lxml:  %r' % (exp,))
                print('  xpx:   %r' % (act,))
    print('lxml comparison: %d cases, %d mismatches' % (total, failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
