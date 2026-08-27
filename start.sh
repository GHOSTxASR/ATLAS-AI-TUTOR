#!/usr/bin/env bash
# Shim. The launcher itself is start.py. See start.py.
cd "$(dirname "$0")"
exec python3 start.py "$@"
