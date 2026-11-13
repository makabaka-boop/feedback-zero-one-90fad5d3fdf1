#!/usr/bin/env python3
"""CLI tests: success replaces the output file, failure keeps the old one."""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(HERE), 'main.py')


def run_main(inp, outp):
    return subprocess.run([sys.executable, MAIN, inp, outp],
                          capture_output=True, text=True)


def main():
    failures = 0
    tmp = tempfile.mkdtemp(prefix='xpx-cli-')
    inp = os.path.join(tmp, 'in.json')
    outp = os.path.join(tmp, 'out.json')

    def expect(cond, label, detail=''):
        nonlocal failures
        if not cond:
            failures += 1
            print('FAIL %s %s' % (label, detail))

    # 1. success creates the output
    with open(inp, 'w', encoding='utf-8') as fh:
        json.dump({'xml': '<r><a/><b/><c/></r>',
                   'queries': ['/r/c/preceding::*[1]', '//a', '/r/x']}, fh)
    proc = run_main(inp, outp)
    expect(proc.returncode == 0, 'success exit', proc.stderr)
    with open(outp, encoding='utf-8') as fh:
        results = json.load(fh)
    expect(results == [[{'path': [1], 'value': ''}],
                       [{'path': [0], 'value': ''}], []],
           'success payload', repr(results))

    # 2. success replaces an existing output
    with open(outp, 'w', encoding='utf-8') as fh:
        fh.write('OLD-CONTENT')
    with open(inp, 'w', encoding='utf-8') as fh:
        json.dump({'xml': '<r/>', 'queries': []}, fh)
    proc = run_main(inp, outp)
    expect(proc.returncode == 0, 'replace exit', proc.stderr)
    with open(outp, encoding='utf-8') as fh:
        expect(json.load(fh) == [], 'replace payload')

    # 3. failure keeps the old file and reports the field path
    with open(outp, 'w', encoding='utf-8') as fh:
        fh.write('KEEP-ME')
    with open(inp, 'w', encoding='utf-8') as fh:
        fh.write('{"xml": "<r>", "queries": []}')
    proc = run_main(inp, outp)
    expect(proc.returncode == 1, 'reject exit', repr(proc.returncode))
    with open(outp, encoding='utf-8') as fh:
        expect(fh.read() == 'KEEP-ME', 'reject keeps file')
    try:
        err = json.loads(proc.stderr)
        expect(err['error']['path'] == '$.xml', 'reject path',
               proc.stderr)
    except (ValueError, KeyError) as exc:
        expect(False, 'reject stderr json', '%r %s' % (exc, proc.stderr))

    # 4. query error also keeps the file
    with open(inp, 'w', encoding='utf-8') as fh:
        json.dump({'xml': '<r/>', 'queries': ['/r', '$x']}, fh)
    proc = run_main(inp, outp)
    expect(proc.returncode == 1, 'query reject exit')
    with open(outp, encoding='utf-8') as fh:
        expect(fh.read() == 'KEEP-ME', 'query reject keeps file')
    err = json.loads(proc.stderr)
    expect(err['error']['path'] == '$.queries[1]', 'query reject path',
           proc.stderr)

    # 5. JSON syntax error reports $
    with open(inp, 'w', encoding='utf-8') as fh:
        fh.write('{broken')
    proc = run_main(inp, outp)
    expect(proc.returncode == 1, 'json reject exit')
    err = json.loads(proc.stderr)
    expect(err['error']['path'] == '$', 'json reject path', proc.stderr)
    with open(outp, encoding='utf-8') as fh:
        expect(fh.read() == 'KEEP-ME', 'json reject keeps file')

    # 6. no leftover temp files
    leftovers = [n for n in os.listdir(tmp) if n.startswith('.xpx-')]
    expect(not leftovers, 'no temp leftovers', repr(leftovers))

    print('cli: %s' % ('FAILED' if failures else 'all passed'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
