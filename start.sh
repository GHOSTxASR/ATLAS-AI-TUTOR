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
export LEARNINGOS_ENV=production
export LEARNINGOS_PORT="${LEARNINGOS_PORT:-8000}"

python -m uvicorn app.main:app --host 127.0.0.1 --port "$LEARNINGOS_PORT"
