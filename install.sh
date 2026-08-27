#!/usr/bin/env bash
# Shim. The installer itself is install.py -- one cross-platform file
# instead of a .bat and a .sh that drift apart. See install.py.
cd "$(dirname "$0")"
exec python3 install.py "$@"
