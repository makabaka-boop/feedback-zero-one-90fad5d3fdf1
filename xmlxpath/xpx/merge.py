"""Three-way merge of offline catalog branches.

When the input object carries a ``merge`` member (exactly the ``base``
and ``other`` XML strings; the top-level ``xml`` member is the local
branch) the three trees are merged before extraction:

* every element carries a non-empty ``id`` attribute, unique within its
  tree; the three trees share the same id set and the same root id;
* no element mixes text and element children (whitespace counts as
  text);
* aligned by id, the name, every non-id attribute, the direct text
  (empty string when absent) and the parent id are resolved three-way:
  equal branches take that value; one branch equal to the base takes the
  other branch; anything else is a conflict.  A missing attribute is
  not the same as an empty-string one;
* for every pair of elements sharing a parent in the merged tree, the
  before/after relation is taken from each tree (pairs that are not
  siblings in a tree record no relation) and resolved the same way; the
  non-empty relations constrain the sibling order, which is emitted by
  repeatedly picking the smallest available id in Unicode code point
  order;
* parent cycles, ordering cycles and mixed content after the merge are
  conflicts.

A tree violating the per-tree constraints rejects with that tree's field
path (``$.xml`` / ``$.merge.base`` / ``$.merge.other``); everything
cross-tree rejects as a conflict with ``$.merge``.
"""

import heapq

from . import xmlmodel
from .errors import Reject

_ABSENT = object()      # attribute not present (distinct from '')
_CONFLICT = object()    # three-way resolution failed


class _Tree(object):
    """One branch, flattened to per-id facts."""

    __slots__ = ('root', 'name', 'attrs', 'text', 'parent', 'sibpos')

    def __init__(self):
        self.root = None
        self.name = {}      # id -> element name
        self.attrs = {}     # id -> {attr name: value} (without id)
        self.text = {}      # id -> direct text ('' when none)
        self.parent = {}    # id -> parent id (None for the root)
        self.sibpos = {}    # id -> index among the parent's element children


def merge_trees(local_xml, base_xml, other_xml):
    """Merge the three branch XML strings; return the merged XML string."""
    local = _extract(local_xml, '$.xml')
    base = _extract(base_xml, '$.merge.base')
    other = _extract(other_xml, '$.merge.other')

    ids = frozenset(local.parent)
    if frozenset(base.parent) != ids or frozenset(other.parent) != ids:
        raise Reject('$.merge', 'the three trees have different id sets')
    if not (base.root == local.root == other.root):
        raise Reject('$.merge', 'the three trees have different root ids')

    name = {}
    parent = {}
    text = {}
    attrs = {}
    for i in ids:
        name[i] = _resolved(base.name[i], local.name[i], other.name[i],
                            'name of element %r' % (i,))
        parent[i] = _resolved(base.parent[i], local.parent[i],
                              other.parent[i], 'parent of element %r' % (i,))
        text[i] = _resolved(base.text[i], local.text[i], other.text[i],
                            'text of element %r' % (i,))
        merged = {}
        for an in set(base.attrs[i]) | set(local.attrs[i]) | set(other.attrs[i]):
            value = _resolved(base.attrs[i].get(an, _ABSENT),
                              local.attrs[i].get(an, _ABSENT),
                              other.attrs[i].get(an, _ABSENT),
                              'attribute %r of element %r' % (an, i))
            if value is not _ABSENT:
                merged[an] = value
        attrs[i] = merged

    _check_parent_cycles(parent)

    children = {}
    for i in ids:
        p = parent[i]
        if p is not None:
            children.setdefault(p, []).append(i)

    for i in ids:
        if text[i] != '' and children.get(i):
            raise Reject('$.merge',
                         'element %r would mix text and element children'
                         % (i,))

    order = {}
    for p, sibs in children.items():
        order[p] = _order_siblings(sibs, base, local, other)

    return _serialize(local.root, name, attrs, text, order)


def _extract(xml_str, path):
    """Parse one branch tree and check the per-tree merge constraints."""
    try:
        doc = xmlmodel.parse(xml_str)
    except Reject as exc:
        raise Reject(path, exc.message)
    tree = _Tree()
    stack = [(doc.root, None)]
    while stack:
        el, pid = stack.pop()
        attrs = {}
        eid = None
        for attr in el.attrs:
            if attr.name == 'id':
                eid = attr.value
            else:
                attrs[attr.name] = attr.value
        if eid is None:
            raise Reject(path, 'element <%s> has no id attribute' % el.name)
        if eid == '':
            raise Reject(path, 'element <%s> has an empty id' % el.name)
        if eid in tree.parent:
            raise Reject(path, 'duplicate id %r' % (eid,))
        text_parts = []
        elem_kids = []
        for child in el.children:
            if isinstance(child, xmlmodel.Text):
                text_parts.append(child.data)
            else:
                elem_kids.append(child)
        if text_parts and elem_kids:
            raise Reject(path,
                         'element <%s> mixes text and element children'
                         % el.name)
        if pid is None:
            tree.root = eid
        tree.name[eid] = el.name
        tree.attrs[eid] = attrs
        tree.text[eid] = ''.join(text_parts)
        tree.parent[eid] = pid
        tree.sibpos[eid] = el.elem_index
        for child in reversed(elem_kids):
            stack.append((child, eid))
    return tree


def _pick(b, l, o):
    """Three-way resolution: equal branches win; one branch equal to the
    base takes the other branch; anything else is a conflict."""
    if l == o:
        return l
    if l == b:
        return o
    if o == b:
        return l
    return _CONFLICT


def _resolved(b, l, o, what):
    value = _pick(b, l, o)
    if value is _CONFLICT:
        raise Reject('$.merge', 'conflict on %s' % what)
    return value


def _check_parent_cycles(parent):
    """Every id must reach the root; a parent cycle is a conflict."""
    done = set()
    on_chain = set()
    for start in parent:
        if start in done:
            continue
        chain = []
        node = start
        while node is not None and node not in done:
            if node in on_chain:
                raise Reject('$.merge', 'parent cycle involving id %r'
                             % (node,))
            on_chain.add(node)
            chain.append(node)
            node = parent[node]
        for i in chain:
            on_chain.discard(i)
            done.add(i)


def _relation(tree, x, y):
    """The pair's order in one tree: ``(first, second)`` or None."""
    if tree.parent[x] != tree.parent[y]:
        return None
    if tree.sibpos[x] < tree.sibpos[y]:
        return (x, y)
    return (y, x)


def _order_siblings(sibs, base, local, other):
    """Order one sibling group per the merged pairwise relations."""
    successors = dict((s, set()) for s in sibs)
    indegree = dict((s, 0) for s in sibs)
    for ai in range(len(sibs)):
        for bi in range(ai + 1, len(sibs)):
            x, y = sibs[ai], sibs[bi]
            rel = _resolved(_relation(base, x, y), _relation(local, x, y),
                            _relation(other, x, y),
                            'order of elements %r and %r' % (x, y))
            if rel is not None:
                first, second = rel
                if second not in successors[first]:
                    successors[first].add(second)
                    indegree[second] += 1
    # Kahn's algorithm; among the available ids take the smallest one in
    # Unicode code point order.
    available = [s for s in sibs if indegree[s] == 0]
    heapq.heapify(available)
    out = []
    while available:
        u = heapq.heappop(available)
        out.append(u)
        for v in successors[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                heapq.heappush(available, v)
    if len(out) != len(sibs):
        raise Reject('$.merge', 'ordering cycle among sibling elements')
    return out


def _serialize(root, name, attrs, text, order):
    """Serialize the merged tree compactly, so that re-parsing the output
    yields exactly the merged tree (no whitespace is introduced and the
    characters that would be normalized on input are escaped)."""
    parts = []
    stack = [(root, False)]
    while stack:
        i, closing = stack.pop()
        if closing:
            parts.append('</%s>' % name[i])
            continue
        all_attrs = dict(attrs[i])
        all_attrs['id'] = i
        attr_str = ''.join(' %s="%s"' % (an, _escape_attr(all_attrs[an]))
                           for an in sorted(all_attrs))
        kids = order.get(i)
        if kids:
            parts.append('<%s%s>' % (name[i], attr_str))
            stack.append((i, True))
            for child in reversed(kids):
                stack.append((child, False))
        elif text[i] != '':
            parts.append('<%s%s>%s</%s>'
                         % (name[i], attr_str, _escape_text(text[i]),
                            name[i]))
        else:
            parts.append('<%s%s/>' % (name[i], attr_str))
    return ''.join(parts)


def _escape_text(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('\r', '&#13;'))


def _escape_attr(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('"', '&quot;').replace('\t', '&#9;')
             .replace('\n', '&#10;').replace('\r', '&#13;'))
