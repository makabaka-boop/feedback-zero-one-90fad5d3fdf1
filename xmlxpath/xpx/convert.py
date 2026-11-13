"""XPath 1.0 type conversions (section 4 of the recommendation).

Values are represented with plain Python types:

* node-set  -> ``list`` of nodes
* number    -> ``float``
* string    -> ``str``
* boolean   -> ``bool``
"""

import math
import re

from . import xmlmodel

_STRING_TO_NUMBER_RE = re.compile(
    r'^[ \t\r\n]*-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)[ \t\r\n]*$')


def string_to_number(s):
    """number(): optional whitespace, optional '-', a Number. No '+'/exp."""
    if _STRING_TO_NUMBER_RE.match(s):
        return float(s.strip(' \t\r\n'))
    return float('nan')


def number_to_string(n):
    """string(number) as specified in section 4.3."""
    if math.isnan(n):
        return 'NaN'
    if math.isinf(n):
        return 'Infinity' if n > 0 else '-Infinity'
    if n == 0:
        return '0'
    if n == math.floor(n) and abs(n) < 1e21:
        return str(int(n))
    s = repr(n)
    if 'e' in s or 'E' in s:
        from decimal import Decimal
        s = format(Decimal(s), 'f')
    return s


def _first_in_document_order(nodes):
    return min(nodes, key=lambda n: n.sort_key)


def to_boolean(v):
    if type(v) is bool:
        return v
    if type(v) is float:
        return v != 0 and not math.isnan(v)
    if type(v) is str:
        return len(v) > 0
    return len(v) > 0                    # node-set


def to_number(v):
    if type(v) is float:
        return v
    if type(v) is bool:
        return 1.0 if v else 0.0
    if type(v) is str:
        return string_to_number(v)
    if not v:                            # empty node-set
        return float('nan')
    return string_to_number(xmlmodel.string_value(_first_in_document_order(v)))


def to_string(v):
    if type(v) is str:
        return v
    if type(v) is bool:
        return 'true' if v else 'false'
    if type(v) is float:
        return number_to_string(v)
    if not v:                            # empty node-set
        return ''
    return xmlmodel.string_value(_first_in_document_order(v))
