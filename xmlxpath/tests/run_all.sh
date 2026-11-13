#!/bin/sh
# Run the full acceptance suite.
set -e
cd "$(dirname "$0")/.."
python3 tests/compare_lxml.py
python3 tests/random_diff.py
python3 tests/test_attr_order.py
python3 tests/test_reject.py
python3 tests/test_spec_conformance.py
python3 tests/test_valid.py
python3 tests/test_cli.py
echo "ALL TESTS PASSED"
