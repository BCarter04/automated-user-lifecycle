#!/usr/bin/env bash
# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
# Demo only. This installer does not contact a tenant and does not install paid software.

set -euo pipefail
cd "$(dirname "$0")"

echo "DEMO ONLY. No tenant is contacted."
echo "Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE."
echo

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3 is not installed."
  echo "Install Python 3, then run this installer again. No other packages are required."
  exit 1
fi

"$PYTHON" --version
mkdir -p data logs reports
if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "Created config.json from the example. It uses a fake tenant."
fi

echo "Checking the sample workflow..."
"$PYTHON" -m unittest tests/test_lifecycle.py

echo
echo "Running the demo..."
"$PYTHON" src/lifecycle.py demo

echo
echo "Ready."
echo "Next:  $PYTHON src/lifecycle.py menu"
echo "Ticket: reports/demo-summary.md"
echo "List:   $PYTHON src/lifecycle.py list"
