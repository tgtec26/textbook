#!/usr/bin/env zsh
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew missing. Install from https://brew.sh first."
  exit 1
fi

brew install openjdk python@3.14

PYTHON_BIN="${PYTHON_BIN:-python3.14}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m venv .venv-opendataloader
. .venv-opendataloader/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo ""
echo "Setup complete."
echo "Run before conversion:"
echo "  export PATH=\"/opt/homebrew/opt/openjdk/bin:$PATH\""
echo "  . .venv-opendataloader/bin/activate"
echo ""
echo "Check:"
echo "  python -c 'import fitz; print(fitz.version)'"
echo "  opendataloader-pdf --help >/dev/null && echo opendataloader-ok"
