#!/usr/bin/env python3
"""Merge-feature acceptance: independent fixtures under merge_fixtures/.

Each fixture file is a JSON object:

    {"name": "...", "input": {<the request object>},
     "expect": {"xml": "<merged xml>", "results": [...]}}   # success
  or
    {"name": "...", "input": {...}, "reject": "<field path>"}  # rejection

For a success fixture the emitted ``xml`` is also re-parsed: evaluating
the same queries against it (without a merge) must reproduce
``results`` -- the emitted XML re-parses to the merged tree.  Two CLI
checks at the end verify the {"xml", "results"} output shape and that a
merge conflict keeps the old output file.
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAIN = os.path.join(ROOT, 'main.py')
FIXTURES = os.path.join(HERE, 'merge_fixtures')

sys.path.insert(0, ROOT)

from xpx import jsonstrict, service
from xpx.errors import Reject


def run_fixture(fx):
    """Run one fixture; return None on success, else a failure message."""
    text = json.dumps(fx['input'], ensure_ascii=False)
    try:
        data = jsonstrict.loads(text)
        xml, queries, merge = service.validate_input(data)
        out = service.run(xml, queries, merge)
    except Reject as exc:
        if 'reject' in fx:
            if exc.path == fx['reject']:
                return None
            return 'rejected with path %r, want %r (%s)' % (
                exc.path, fx['reject'], exc.message)
        return 'unexpected rejection %s: %s' % (exc.path, exc.message)
    if 'reject' in fx:
        return 'input was ACCEPTED, want rejection at %s' % (fx['reject'],)
    want = fx['expect']
    if out != want:
        return 'output mismatch:\n  got  %r\n  want %r' % (out, want)
    # the emitted xml must re-parse to the merged tree: same results
    again = service.run(out['xml'], queries)
    if again != out['results']:
        return 're-parse mismatch:\n  got  %r\n  want %r' % (
            again, out['results'])
    return None


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as fh:
        return json.load(fh)


def cli_checks():
    """End-to-end through main.py; returns the number of failures."""
    failures = 0

    def expect(cond, label, detail=''):
        nonlocal failures
        if not cond:
            failures += 1
            print('FAIL cli %s %s' % (label, detail))

    tmp = tempfile.mkdtemp(prefix='xpx-merge-')
    inp = os.path.join(tmp, 'in.json')
    outp = os.path.join(tmp, 'out.json')

    # 1. merge success: the output object has exactly {xml, results}
    fx = load_fixture('01_move.json')
    with open(inp, 'w', encoding='utf-8') as fh:
        json.dump(fx['input'], fh, ensure_ascii=False)
    proc = subprocess.run([sys.executable, MAIN, inp, outp],
                          capture_output=True, text=True)
    expect(proc.returncode == 0, 'merge exit', proc.stderr)
    with open(outp, encoding='utf-8') as fh:
        got = json.load(fh)
    expect(got == fx['expect'], 'merge payload', repr(got))

    # 2. merge conflict: whole run rejected, old output file kept
    with open(outp, 'w', encoding='utf-8') as fh:
        fh.write('KEEP-ME')
    fx = load_fixture('04_order_cycle.json')
    with open(inp, 'w', encoding='utf-8') as fh:
        json.dump(fx['input'], fh, ensure_ascii=False)
    proc = subprocess.run([sys.executable, MAIN, inp, outp],
                          capture_output=True, text=True)
    expect(proc.returncode == 1, 'conflict exit', repr(proc.returncode))
    with open(outp, encoding='utf-8') as fh:
        expect(fh.read() == 'KEEP-ME', 'conflict keeps file')
    try:
        err = json.loads(proc.stderr)
        expect(err['error']['path'] == '$.merge', 'conflict path',
               proc.stderr)
    except (ValueError, KeyError) as exc:
        expect(False, 'conflict stderr json', '%r %s' % (exc, proc.stderr))

    # 3. no merge member: the output stays the plain results array
    with open(inp, 'w', encoding='utf-8') as fh:
        json.dump({'xml': '<r/>', 'queries': ['/r']}, fh)
    proc = subprocess.run([sys.executable, MAIN, inp, outp],
                          capture_output=True, text=True)
    expect(proc.returncode == 0, 'compat exit', proc.stderr)
    with open(outp, encoding='utf-8') as fh:
        got = json.load(fh)
    expect(got == [[{'path': [], 'value': ''}]], 'compat payload', repr(got))
    return failures


def main():
    failures = 0
    files = sorted(glob.glob(os.path.join(FIXTURES, '*.json')))
    if not files:
        print('FAIL no fixtures found in %s' % FIXTURES)
        return 1
    for path in files:
        with open(path, encoding='utf-8') as fh:
            fx = json.load(fh)
        problem = run_fixture(fx)
        if problem is not None:
            failures += 1
            print('FAIL %s (%s)\n     %s' % (
                os.path.basename(path), fx.get('name', '?'), problem))
    failures += cli_checks()
    print('merge: %d fixtures, %s' % (
        len(files), 'FAILED' if failures else 'all passed'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
