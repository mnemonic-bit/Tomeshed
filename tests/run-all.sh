#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin=${TOMESHED_TEST_PYTHON:-.venv/bin/python}
if [[ ! -x "$python_bin" ]]; then python_bin=python3; fi
"$python_bin" -m pytest -q tests/test_*.py
tests/container/check-lock.sh
for check in tests/browser_check*.py; do
    "$python_bin" "$check"
done
tests/container/smoke.sh --build
