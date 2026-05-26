# Textbook PDF to Markdown Converter

Korean textbook PDF conversion workflow.

## What This Repo Contains

- `run_drive_conversion.py`: final conversion, unit splitting, and Google Drive upload flow
- `process_drive_textbooks.py`: Google Drive inventory/download helpers
- `convert_textbook_pdf.py`: earlier two-up conversion helper
- `test_convert_textbook_pdf.py`: focused regression tests
- `TEXTBOOK_PDF_TO_MD_WORKFLOW.md`: setup and operating guide

## What Is Excluded

PDFs, generated Markdown textbooks, Google Drive manifests, and local reports are excluded by `.gitignore`.

Those files may contain copyrighted textbook content or private Drive IDs.

## Quick Start

See [TEXTBOOK_PDF_TO_MD_WORKFLOW.md](TEXTBOOK_PDF_TO_MD_WORKFLOW.md).
