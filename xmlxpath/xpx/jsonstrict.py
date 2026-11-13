"""Strict JSON parsing.

Hand-written (instead of :mod:`json`) so that we can:

* reject duplicate object members and report the member path,
* reject lone UTF-16 surrogates inside ``\\uXXXX`` escapes and report the
  path of the offending string,
* reject anything else (syntax errors) with path ``$``.

Only the JSON RFC 8259 grammar is accepted: no NaN/Infinity, no trailing
commas, no control characters inside strings, whitespace limited to
space/tab/CR/LF.
"""

from .errors import Reject

_WS = ' \t\n\r'
_HEX = frozenset('0123456789abcdefABCDEF')
_MAX_DEPTH = 100


def keypath(path, key):
    """Append an object member to a JSON-ish path."""
    if key.isascii() and (key.isidentifier()):
        return '%s.%s' % (path, key)
    import json as _json
    return '%s[%s]' % (path, _json.dumps(key, ensure_ascii=True))


def loads(text):
    """Parse *text* (a ``str``) strictly; raise :class:`Reject` on errors."""
    return _Parser(text).parse()


class _Parser(object):
    def __init__(self, text):
        self.s = text
        self.n = len(text)
        self.i = 0

    # -- helpers ---------------------------------------------------------
    def error(self, message):
        raise Reject('$', message)

    def ws(self):
        s, n, i = self.s, self.n, self.i
        while i < n and s[i] in _WS:
            i += 1
        self.i = i

    def parse(self):
        self.ws()
        value = self.value('$', 0)
        self.ws()
        if self.i != self.n:
            self.error('unexpected trailing characters')
        return value

    # -- values ----------------------------------------------------------
    def value(self, path, depth):
        if depth > _MAX_DEPTH:
            self.error('nesting too deep')
        if self.i >= self.n:
            self.error('unexpected end of input')
        c = self.s[self.i]
        if c == '{':
            return self.obj(path, depth)
        if c == '[':
            return self.arr(path, depth)
        if c == '"':
            return self.string(path)
        if c == 't':
            return self.literal('true', True)
        if c == 'f':
            return self.literal('false', False)
        if c == 'n':
            return self.literal('null', None)
        if c == '-' or c.isdigit():
            return self.number()
        self.error('unexpected character %r' % (c,))

    def literal(self, word, value):
        if self.s.startswith(word, self.i):
            self.i += len(word)
            return value
        self.error('invalid literal')

    def number(self):
        s, n = self.s, self.n
        start = self.i
        i = start
        if s[i] == '-':
            i += 1
        if i >= n or not s[i].isdigit():
            self.error('invalid number')
        if s[i] == '0':
            i += 1
        else:
            while i < n and s[i].isdigit():
                i += 1
        if i < n and s[i] == '.':
            i += 1
            if i >= n or not s[i].isdigit():
                self.error('invalid number')
            while i < n and s[i].isdigit():
                i += 1
        if i < n and s[i] in 'eE':
            i += 1
            if i < n and s[i] in '+-':
                i += 1
            if i >= n or not s[i].isdigit():
                self.error('invalid number')
            while i < n and s[i].isdigit():
                i += 1
        self.i = i
        return float(s[start:i])

    def string(self, path):
        # self.s[self.i] == '"'
        self.i += 1
        out = []
        s, n = self.s, self.n
        while True:
            if self.i >= n:
                self.error('unterminated string')
            c = s[self.i]
            if c == '"':
                self.i += 1
                return ''.join(out)
            if c == '\\':
                self.i += 1
                if self.i >= n:
                    self.error('bad escape')
                e = s[self.i]
                self.i += 1
                if e == '"':
                    out.append('"')
                elif e == '\\':
                    out.append('\\')
                elif e == '/':
                    out.append('/')
                elif e == 'b':
                    out.append('\b')
                elif e == 'f':
                    out.append('\f')
                elif e == 'n':
                    out.append('\n')
                elif e == 'r':
                    out.append('\r')
                elif e == 't':
                    out.append('\t')
                elif e == 'u':
                    out.append(self.unicode_escape(path))
                else:
                    self.error('bad escape \\%s' % e)
            elif ord(c) < 0x20:
                self.error('unescaped control character in string')
            else:
                out.append(c)
                self.i += 1

    def unicode_escape(self, path):
        cp = self.hex4()
        if 0xD800 <= cp <= 0xDBFF:
            # a high surrogate must be followed immediately by a low one
            if self.i + 1 < self.n and self.s[self.i] == '\\' \
                    and self.s[self.i + 1] == 'u':
                self.i += 2
                lo = self.hex4()
                if 0xDC00 <= lo <= 0xDFFF:
                    return chr(0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00))
                raise Reject(path, 'lone surrogate in string')
            raise Reject(path, 'lone surrogate in string')
        if 0xDC00 <= cp <= 0xDFFF:
            raise Reject(path, 'lone surrogate in string')
        return chr(cp)

    def hex4(self):
        if self.i + 4 > self.n:
            self.error('bad \\u escape')
        chunk = self.s[self.i:self.i + 4]
        if any(ch not in _HEX for ch in chunk):
            self.error('bad \\u escape')
        self.i += 4
        return int(chunk, 16)

    def obj(self, path, depth):
        self.i += 1
        result = {}
        self.ws()
        if self.i < self.n and self.s[self.i] == '}':
            self.i += 1
            return result
        while True:
            self.ws()
            if self.i >= self.n or self.s[self.i] != '"':
                self.error('expected object key')
            key = self.string(path)
            self.ws()
            if self.i >= self.n or self.s[self.i] != ':':
                self.error("expected ':'")
            self.i += 1
            self.ws()
            kpath = keypath(path, key)
            if key in result:
                raise Reject(kpath, 'duplicate member')
            result[key] = self.value(kpath, depth + 1)
            self.ws()
            if self.i >= self.n:
                self.error('unterminated object')
            c = self.s[self.i]
            if c == ',':
                self.i += 1
                continue
            if c == '}':
                self.i += 1
                return result
            self.error("expected ',' or '}'")

    def arr(self, path, depth):
        self.i += 1
        result = []
        self.ws()
        if self.i < self.n and self.s[self.i] == ']':
            self.i += 1
            return result
        while True:
            self.ws()
            result.append(self.value('%s[%d]' % (path, len(result)), depth + 1))
            self.ws()
            if self.i >= self.n:
                self.error('unterminated array')
            c = self.s[self.i]
            if c == ',':
                self.i += 1
                continue
            if c == ']':
                self.i += 1
                return result
            self.error("expected ',' or ']'")
