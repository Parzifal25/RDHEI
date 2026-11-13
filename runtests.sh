#!/usr/bin/env bash
set -o pipefail
echo "probe: python3 available? $(command -v python3)"
echo "probe: pytest available? $(command -v pytest || true)"
echo "probe: project test files:"
find . -maxdepth 3 -type f \( -name "test_*.py" -o -name "*_test.py" -o -name "tests.py" -o -name "*tests.py" \) | sed 's#^\./##' | sort
