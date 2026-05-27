# Textbook PDF to Markdown Converter

Korean textbook PDF conversion workflow.

## What This Repo Contains

- `convert_local.py`: local-folder conversion flow for Mac Studio / external drives
- `run_drive_conversion.py`: final conversion, unit splitting, and Google Drive upload flow
- `process_drive_textbooks.py`: Google Drive inventory/download helpers
- `convert_textbook_pdf.py`: earlier two-up conversion helper
- `test_convert_textbook_pdf.py`: focused regression tests
- `REPRODUCIBILITY.md`: local setup and repeatable conversion guide
- `TEXTBOOK_PDF_TO_MD_WORKFLOW.md`: setup and operating guide

## What Is Excluded

PDFs, generated Markdown textbooks, Google Drive manifests, and local reports are excluded by `.gitignore`.

Those files may contain copyrighted textbook content or private Drive IDs.

## Quick Start

Local Mac Studio work:

```sh
./setup_mac.sh
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
. .venv-opendataloader/bin/activate
python convert_local.py --input "/path/to/pdf_root" --output "/path/to/output_md" --reports "/path/to/reports"
```

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for local work.
See [TEXTBOOK_PDF_TO_MD_WORKFLOW.md](TEXTBOOK_PDF_TO_MD_WORKFLOW.md) for the older Google Drive flow.
