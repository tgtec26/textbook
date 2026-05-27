#!/usr/bin/env zsh
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: ./run_local_conversion.sh <pdf_folder> <output_folder> <reports_folder> [--keep-output]"
  exit 1
fi

PDF_FOLDER="$1"
OUTPUT_FOLDER="$2"
REPORTS_FOLDER="$3"
KEEP_OUTPUT="${4:-}"

export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

if [ ! -d ".venv-opendataloader" ]; then
  ./setup_mac.sh
fi

. .venv-opendataloader/bin/activate

if [ "$KEEP_OUTPUT" = "--keep-output" ]; then
  python convert_local.py \
    --input "$PDF_FOLDER" \
    --output "$OUTPUT_FOLDER" \
    --reports "$REPORTS_FOLDER"
else
  python convert_local.py \
    --input "$PDF_FOLDER" \
    --output "$OUTPUT_FOLDER" \
    --reports "$REPORTS_FOLDER" \
    --clean-output
fi
