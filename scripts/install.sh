#!/usr/bin/env bash
# Shim. The install script itself is install.py in the repository root -- one
# cross-platform file rather than a .bat and a .sh that drift apart.
cd "$(dirname "$0")/.."

# python3 on most systems, but not all of them have it under that name.
if command -v python3 >/dev/null 2>&1; then
  exec python3 install.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python install.py "$@"
else
  echo "Python 3.11+ is required but was not found on PATH." >&2
  echo "Install it from https://www.python.org/downloads/" >&2
  exit 1
fi
