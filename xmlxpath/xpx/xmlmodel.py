"""Restricted XML 1.0 parsing and the node model used by the evaluator.

The XML subset enforced here (XML 1.0, 5th edition):

* optional XML declaration, ``version="1.0"``, encoding must be UTF-8;
* no DOCTYPE, no comments, no processing instructions;
* no namespace declarations (``xmlns``) and no colon names;
* CDATA sections, character references and the five predefined entities
  are allowed (handled by expat);
* whitespace is preserved; adjacent character data (including CDATA) is
  merged into a single text node;
* the attributes of an element are kept sorted by name in Unicode code
  point order (this also defines their document order).

The tree contains four node kinds: ``Document``, ``Element``, ``Text`` and
``Attribute``.  Every node gets a ``sort_key`` that totally orders the
whole tree in document order (attributes sort right after their owner
element, in code point order of their names).
"""

from xml.parsers import expat

from .errors import Reject

XML_PATH = '$.xml'


def _fail(message):
    raise Reject(XML_PATH, message)


class Node(object):
    __slots__ = ()


class Document(Node):
    __slots__ = ('children', 'parent', 'order', 'sort_key', 'subtree_end',
                 'by_order', 'root', 'doc', 'sv')

    def __init__(self):
        self.children = []        # exactly one Element after a valid parse
        self.parent = None
        self.order = 0
        self.sort_key = (0, 0)
        self.subtree_end = 0
        self.by_order = []        # by_order[i] == node with order i
        self.root = None
        self.doc = self
        self.sv = None            # memoized string-value


class Element(Node):
    __slots__ = ('name', 'attrs', 'children', 'parent', 'order', 'sort_key',
                 'subtree_end', 'elem_children', 'elem_index', 'doc', 'sv')

    def __init__(self, name):
        self.name = name
        self.attrs = []           # Attribute nodes, sorted by name
        self.children = []        # Element/Text nodes in document order
        self.parent = None
        self.order = 0
        self.sort_key = (0, 0)
        self.subtree_end = 0
        self.elem_children = []
        self.elem_index = 0
        self.doc = None
        self.sv = None            # memoized string-value


class Text(Node):
    __slots__ = ('data', 'parent', 'order', 'sort_key', 'doc')

    def __init__(self, data):
        self.data = data
        self.parent = None
        self.order = 0
        self.sort_key = (0, 0)
        self.doc = None


class Attribute(Node):
    # ``parent`` is the owner element, as required by XPath 1.0.
    __slots__ = ('name', 'value', 'parent', 'rank', 'sort_key', 'doc')

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.parent = None
        self.rank = 0
        self.sort_key = (0, 0)
        self.doc = None


def parse(xml_str):
    """Parse *xml_str* into a :class:`Document`; raise :class:`Reject`."""
    doc = Document()
    stack = [doc]

    def start_element(name, attrs):
        if ':' in name:
            _fail('prefixed name not allowed: %r' % name)
        el = Element(name)
        items = []
        for aname, value in attrs.items():
            if ':' in aname:
                _fail('prefixed name not allowed: %r' % aname)
            if aname == 'xmlns':
                _fail('namespace declaration not allowed')
            items.append((aname, value))
        items.sort(key=lambda kv: kv[0])   # Unicode code point order
        el.attrs = []
        for aname, value in items:
            attr = Attribute(aname, value)
            attr.parent = el
            el.attrs.append(attr)
        parent = stack[-1]
        el.parent = parent
        parent.children.append(el)
        stack.append(el)

    def end_element(name):
        stack.pop()

    def char_data(data):
        if not data:
            return
        parent = stack[-1]
        if isinstance(parent, Document):
            # whitespace around the root element: not part of the XPath
            # data model (non-whitespace is rejected by expat itself)
            return
        last = parent.children[-1] if parent.children else None
        if isinstance(last, Text):
            last.data += data           # merge adjacent character data
        else:
            t = Text(data)
            t.parent = parent
            parent.children.append(t)

    def xml_decl(version, encoding, standalone):
        if version != '1.0':
            _fail('unsupported XML version: %r' % version)
        if encoding is not None and encoding.lower() != 'utf-8':
            _fail('unsupported encoding: %r' % encoding)

    p = expat.ParserCreate()
    p.buffer_text = True
    p.XmlDeclHandler = xml_decl
    p.StartDoctypeDeclHandler = lambda *a: _fail('DOCTYPE not allowed')
    p.CommentHandler = lambda *a: _fail('comment not allowed')
    p.ProcessingInstructionHandler = \
        lambda *a: _fail('processing instruction not allowed')
    p.StartElementHandler = start_element
    p.EndElementHandler = end_element
    p.CharacterDataHandler = char_data
    try:
        p.Parse(xml_str.encode('utf-8'), True)
    except Reject:
        raise
    except expat.ExpatError as exc:
        _fail('not well-formed: %s' % exc)

    doc.root = doc.children[0]
    _index(doc)
    return doc


def _index(doc):
    """Assign document-order positions and precompute helper tables."""
    counter = 1
    seq = []
    stack = [(doc, iter(doc.children))]
    while stack:
        node, it = stack[-1]
        advanced = False
        for child in it:
            child.order = counter
            counter += 1
            child.sort_key = (child.order, 0)
            child.doc = doc
            seq.append(child)
            if isinstance(child, Element):
                stack.append((child, iter(child.children)))
            advanced = True
            break
        if not advanced:
            node.subtree_end = counter - 1
            stack.pop()
    doc.subtree_end = counter - 1
    doc.by_order = [doc] + seq
    for node in seq:
        if isinstance(node, Element):
            for rank, attr in enumerate(node.attrs):
                attr.rank = rank
                attr.sort_key = (node.order, rank + 1)
                attr.doc = doc
            node.elem_children = [c for c in node.children
                                  if isinstance(c, Element)]
            for idx, child in enumerate(node.elem_children):
                child.elem_index = idx


# ---------------------------------------------------------------------------
# XPath data-model helpers

def string_value(node):
    """XPath 1.0 string-value of a node.

    For elements and the document this is the concatenation of all
    descendant text in document order; the values are memoized per node
    (the whole subtree is computed in one iterative pass), so repeated
    evaluations over the same document stay linear overall.
    """
    if isinstance(node, Attribute):
        return node.value
    if isinstance(node, Text):
        return node.data
    if node.sv is not None:
        return node.sv
    # iterative post-order over the subtree, filling every sv on the way
    stack = [(node, False)]
    while stack:
        current, processed = stack.pop()
        if processed:
            parts = []
            for child in current.children:
                if isinstance(child, Text):
                    parts.append(child.data)
                else:
                    parts.append(child.sv)
            current.sv = ''.join(parts)
        else:
            if current.sv is not None:
                continue
            stack.append((current, True))
            for child in current.children:
                if isinstance(child, Element) and child.sv is None:
                    stack.append((child, False))
    return node.sv


def path_of(elem):
    """Zero-based element-child path; the document element maps to []."""
    parts = []
    node = elem
    while isinstance(node.parent, Element):
        parts.append(node.elem_index)
        node = node.parent
    parts.reverse()
    return parts


def _ancestors(node):
    out = []
    p = node.parent
    while p is not None:
        out.append(p)
        p = p.parent
    return out


def axis_nodes(axis, node):
    """The (unfiltered) axis, in axis order (reverse axes reversed)."""
    if axis == 'self':
        return [node]
    if axis == 'parent':
        return [node.parent] if node.parent is not None else []
    if axis == 'child':
        if isinstance(node, (Document, Element)):
            return list(node.children)
        return []
    if axis == 'attribute':
        if isinstance(node, Element):
            return list(node.attrs)
        return []
    if axis == 'descendant':
        if isinstance(node, (Document, Element)):
            return node.doc.by_order[node.order + 1: node.subtree_end + 1]
        return []
    if axis == 'descendant-or-self':
        return [node] + axis_nodes('descendant', node)
    if axis == 'ancestor':
        return _ancestors(node)
    if axis == 'ancestor-or-self':
        return [node] + _ancestors(node)
    if axis == 'following-sibling':
        if isinstance(node, Attribute) or node.parent is None:
            return []
        sibs = node.parent.children
        return sibs[sibs.index(node) + 1:]
    if axis == 'preceding-sibling':
        if isinstance(node, Attribute) or node.parent is None:
            return []
        sibs = node.parent.children
        i = sibs.index(node)
        return sibs[i - 1::-1] if i else []
    if axis == 'following':
        doc = node.doc
        if isinstance(node, Document):
            return []
        if isinstance(node, Attribute):
            # the attribute sits right after its owner in document order
            return doc.by_order[node.parent.order + 1:]
        if isinstance(node, Element):
            return doc.by_order[node.subtree_end + 1:]
        return doc.by_order[node.order + 1:]
    if axis == 'preceding':
        doc = node.doc
        if isinstance(node, Document):
            return []
        if isinstance(node, Attribute):
            limit = node.parent.order
        else:
            limit = node.order
        excluded = set(id(a) for a in _ancestors(node))
        out = [n for n in doc.by_order[1:limit] if id(n) not in excluded]
        out.reverse()               # reverse axis: reverse document order
        return out
    raise AssertionError('unknown axis %r' % (axis,))
