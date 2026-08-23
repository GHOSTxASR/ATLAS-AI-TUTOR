#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

echo "[Atlas] Checking Python..."
python3 --version >/dev/null

echo "[Atlas] Creating backend virtual environment..."
if [ ! -d "backend/.venv" ]; then
  python3 -m venv backend/.venv
fi

echo "[Atlas] Installing backend dependencies..."
source backend/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

echo "[Atlas] Checking Node.js..."
node --version >/dev/null

echo "[Atlas] Installing frontend dependencies..."
(cd frontend && npm install && npm run build)

echo "[Atlas] Initializing local data directories..."
PYTHONPATH=backend python -m app.config --init-data

echo "[Atlas] Checking Tesseract OCR (optional)..."
if command -v tesseract >/dev/null 2>&1; then
  TESSERACT_PATH="$(command -v tesseract)"
  echo "[Atlas] Tesseract OCR found: $TESSERACT_PATH"
else
  echo "[Atlas] WARNING: Tesseract OCR was not found."
  echo "  OCR for images and scanned PDFs will be unavailable until you install it."
  if command -v apt-get >/dev/null 2>&1; then
    echo "  Install with: sudo apt-get install -y tesseract-ocr"
  elif command -v dnf >/dev/null 2>&1; then
    echo "  Install with: sudo dnf install -y tesseract"
  elif command -v brew >/dev/null 2>&1; then
    echo "  Install with: brew install tesseract"
  else
    echo "  See: https://github.com/tesseract-ocr/tesseract"
  fi
  echo "  Text PDF, DOCX, and TXT uploads keep working without it."
fi

echo "[Atlas] Setup complete."
