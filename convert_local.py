#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import fitz

from run_drive_conversion import convert_book, split_units


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_pdfs(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.rglob("*.pdf") if p.is_file())


def subject_for(input_dir: Path, pdf_path: Path) -> str:
    rel = pdf_path.relative_to(input_dir)
    return rel.parts[0] if len(rel.parts) > 1 else "_unsorted"


def version_info() -> dict:
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pymupdf": fitz.version,
        "opendataloader_pdf": None,
        "java": None,
        "git_commit": None,
    }
    try:
        proc = subprocess.run(
            ["opendataloader-pdf", "--help"],
            text=True,
            capture_output=True,
            timeout=20,
        )
        if proc.returncode == 0:
            info["opendataloader_pdf"] = "available"
    except Exception:
        info["opendataloader_pdf"] = "unavailable"
    try:
        proc = subprocess.run(["java", "-version"], text=True, capture_output=True, timeout=20)
        info["java"] = (proc.stderr or proc.stdout).splitlines()[:3]
    except Exception:
        info["java"] = "unavailable"
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, timeout=20)
        if proc.returncode == 0:
            info["git_commit"] = proc.stdout.strip()
    except Exception:
        pass
    return info


def convert_one(input_dir: Path, output_dir: Path, reports_dir: Path, pdf_path: Path) -> dict:
    subject = subject_for(input_dir, pdf_path)
    stem = pdf_path.stem
    book_dir = output_dir / subject / stem
    book_dir.mkdir(parents=True, exist_ok=True)

    full_md, meta = convert_book(pdf_path, book_dir)
    full_path = book_dir / f"{stem}.md"
    full_path.write_text(full_md, encoding="utf-8")
    unit_files, checks = split_units(stem, full_md, book_dir / "units")

    report = {
        "subject": subject,
        "pdf": str(pdf_path),
        "pdf_name": pdf_path.name,
        "sha256": sha256(pdf_path),
        **meta,
        "unit_count": len(unit_files),
        "full_markdown": str(full_path),
        "unit_files": [str(p) for p in unit_files],
        "offset_checks": checks,
    }
    report_path = reports_dir / f"local_{subject}_{stem}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def write_manifest(reports: list[dict], reports_dir: Path) -> None:
    rows = ["subject\tpdf_name\tsha256\tengine\tmode\toffset\tunit_count\tpath"]
    for report in reports:
        rows.append(
            "\t".join(
                [
                    report["subject"],
                    report["pdf_name"],
                    report["sha256"],
                    report["engine"],
                    report["mode"],
                    str(report["offset"]),
                    str(report["unit_count"]),
                    report["pdf"],
                ]
            )
        )
    (reports_dir / "pdf_checksums.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (reports_dir / "local_summary.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert local textbook PDFs to unit Markdown files.")
    parser.add_argument("--input", required=True, help="Root folder containing PDFs, optionally grouped by subject.")
    parser.add_argument("--output", default="local_output_md", help="Output folder for Markdown files.")
    parser.add_argument("--reports", default="local_reports", help="Output folder for reports/checksums.")
    parser.add_argument("--start-at", default="", help="Start at this relative PDF path or stem.")
    parser.add_argument("--end-at", default="", help="Stop after this relative PDF path or stem.")
    parser.add_argument("--clean-output", action="store_true", help="Remove output/reports folders before conversion.")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    reports_dir = Path(args.reports).expanduser().resolve()
    if not input_dir.exists():
        raise SystemExit(f"input folder not found: {input_dir}")
    if args.clean_output:
        shutil.rmtree(output_dir, ignore_errors=True)
        shutil.rmtree(reports_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    pdfs = list_pdfs(input_dir)
    if not pdfs:
        raise SystemExit(f"no PDF files found: {input_dir}")

    (reports_dir / "environment.json").write_text(json.dumps(version_info(), ensure_ascii=False, indent=2), encoding="utf-8")

    reports = []
    started = not bool(args.start_at)
    for pdf_path in pdfs:
        rel = str(pdf_path.relative_to(input_dir))
        marker = f"{subject_for(input_dir, pdf_path)}/{pdf_path.stem}"
        if not started:
            if args.start_at in {rel, marker, pdf_path.stem}:
                started = True
            else:
                print(f"skip {rel}", flush=True)
                continue

        print(f"convert {rel}", flush=True)
        report = convert_one(input_dir, output_dir, reports_dir, pdf_path)
        reports.append(report)
        print(
            f"done {rel}: {report['engine']} units={report['unit_count']} sha256={report['sha256'][:12]}",
            flush=True,
        )

        if args.end_at and args.end_at in {rel, marker, pdf_path.stem}:
            break

    write_manifest(reports, reports_dir)
    print(f"summary {len(reports)} PDFs, {sum(r['unit_count'] for r in reports)} Markdown units", flush=True)
    print(f"output {output_dir}", flush=True)
    print(f"reports {reports_dir}", flush=True)


if __name__ == "__main__":
    main()
