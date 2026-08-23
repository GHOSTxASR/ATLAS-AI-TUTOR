#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ ! -d "backend/.venv" ]; then
  echo "Backend virtual environment not found. Run ./setup.sh first."
  exit 1
fi

source backend/.venv/bin/activate
export PYTHONPATH="$PWD/backend"
export ATLAS_ENV=production
export ATLAS_PORT="${ATLAS_PORT:-8000}"

python -m uvicorn app.main:app --host 127.0.0.1 --port "$ATLAS_PORT"
