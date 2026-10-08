#!/usr/bin/env bash
# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Double-click or run this. It opens the first-run window. No other command.
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 src/gui.py
elif command -v python >/dev/null 2>&1; then
  exec python src/gui.py
fi
echo "Python 3 is not installed. Install Python 3, then open Start-Here again."
exit 1
