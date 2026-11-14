#!/usr/bin/env python3
"""Entry point of the XML catalog extraction backend.

Usage:

    python3 main.py INPUT_JSON OUTPUT_JSON

INPUT_JSON must be a UTF-8 JSON object with two members plus an
optional third:

    {"xml": "<xml string>", "queries": ["<xpath>", ...],
     "merge": {"base": "<xml string>", "other": "<xml string>"}}

With "merge" present the three branch trees ("xml" is the local branch)
are merged first; the output is then
{"xml": "<merged xml>", "results": [...]} instead of the plain results
array.  Conflicts reject with path "$.merge".

On success the results (one entry per query, in order; each entry
is a list of {"path": [...], "value": "..."} objects) are written to
OUTPUT_JSON as UTF-8 JSON, replacing it atomically.  On any rejection
(JSON syntax, schema, XML or query errors, merge conflicts) nothing is
written -- the old OUTPUT_JSON is kept -- and an error object with the
offending field path is printed to stderr:

    {"error": {"path": "$.queries[0]", "message": "..."}}

Exit status: 0 on success, 1 on rejection, 2 on usage errors.
"""

import json
import os
import sys
import tempfile

# XPath expressions are evaluated by recursion over the AST; allow deep
# (but bounded) nesting.  On Python 3.11+ pure-Python recursion does not
# consume the C stack, so a high limit is safe; anything deeper is
# rejected cleanly with the query's field path.
sys.setrecursionlimit(100000)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xpx import jsonstrict, service                    # noqa: E402
from xpx.errors import Reject                          # noqa: E402


def _report(path, message):
    sys.stderr.write(json.dumps(
        {'error': {'path': path, 'message': message}},
        ensure_ascii=True) + '\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: main.py INPUT_JSON OUTPUT_JSON\n')
        return 2
    input_path, output_path = argv[1], argv[2]

    try:
        with open(input_path, 'rb') as fh:
            raw = fh.read()
    except OSError as exc:
        _report('$', 'cannot read input: %s' % exc)
        return 1

    try:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise Reject('$', 'input is not valid UTF-8')
        data = jsonstrict.loads(text)
        xml, queries, merge = service.validate_input(data)
        results = service.run(xml, queries, merge)
    except Reject as exc:
        _report(exc.path, exc.message)
        return 1

    payload = json.dumps(results, ensure_ascii=False, indent=None) + '\n'

    # success: replace the output atomically; on any I/O failure the old
    # file is left untouched
    out_dir = os.path.dirname(os.path.abspath(output_path))
    try:
        fd, tmp = tempfile.mkstemp(dir=out_dir, prefix='.xpx-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(payload)
            os.replace(tmp, output_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        _report('$', 'cannot write output: %s' % exc)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
