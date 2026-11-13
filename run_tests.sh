#!/usr/bin/env bash
set -o pipefail

echo "== python3 =="
command -v python3 || echo "MISSING"
echo
echo "== pytest =="
command -v pytest || echo "MISSING"
echo
echo "== discovered test files =="
find . -maxdepth 3 -type f \( -name "test_*.py" -o -name "*_test.py" \) | sed 's#^\./##' | sort || true
echo

ran=0
if command -v pytest >/dev/null 2>&1; then
  echo "== running pytest (project root) =="
  pytest -q || true
  ran=1
fi

if [ "$ran" = "0" ] && command -v python3 >/dev/null 2>&1; then
  echo "== running unittest discovery =="
  python3 -m unittest discover -v 2>&1 || true
fi
