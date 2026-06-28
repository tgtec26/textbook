#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

from convert_green_from_preflight import load_existing_reports
from convert_local import combined_sha256, sha256, version_info, write_manifest
from run_drive_conversion import clean_text, convert_book, page_blocks, safe_name


def subject_for_relative(relative_path: str) -> str:
    parts = Path(relative_path).parts
    return parts[0] if len(parts) > 1 else "_unsorted"


def candidate_output_path(output_dir: Path, candidate: dict) -> Path:
    subject = subject_for_relative(candidate["pdfs"][0]["relative_path"])
    book_key = candidate["book_key"]
    return output_dir / subject / book_key / f"{book_key}.md"


def load_auto_candidates(grouping_path: Path, input_dir: Path) -> list[dict]:
    report = json.loads(grouping_path.read_text(encoding="utf-8"))
    candidates = []
    for candidate in report.get("candidates", []):
        if candidate.get("status") != "auto_group_candidate":
            continue
        if "부도" in candidate.get("book_key", ""):
            continue
        existing_pdfs = []
        for item in candidate.get("pdfs", []):
            path = input_dir / item["relative_path"]
            if path.exists():
                existing_pdfs.append({**item, "path": str(path)})
        if len(existing_pdfs) >= 2:
            candidates.append({**candidate, "pdfs": existing_pdfs})
    return candidates


def convert_auto_candidate(input_dir: Path, output_dir: Path, reports_dir: Path, candidate: dict) -> dict:
    subject = subject_for_relative(candidate["pdfs"][0]["relative_path"])
    book_key = candidate["book_key"]
    pdf_paths = [Path(item["path"]) for item in candidate["pdfs"]]
    book_dir = output_dir / subject / book_key
    parts_dir = book_dir / "_parts"
    units_dir = book_dir / "units"
    book_dir.mkdir(parents=True, exist_ok=True)
    units_dir.mkdir(parents=True, exist_ok=True)
    for old in units_dir.glob("*.md"):
        old.unlink()

    full_chunks = [f"# {book_key}", ""]
    unit_files = []
    offset_checks = []
    source_reports = []
    engine_values = []
    mode_values = []
    offset_values = []

    for idx, item in enumerate(candidate["pdfs"], start=1):
        pdf_path = Path(item["path"])
        unit_label = item.get("unit_label") or pdf_path.stem
        part_md, meta = convert_book(pdf_path, parts_dir / pdf_path.stem)
        blocks = page_blocks(part_md)
        pages = sorted(blocks)
        start = pages[0] if pages else 1
        end = pages[-1] if pages else start

        unit_chunks = [f"# {idx}. {unit_label}", ""]
        for page in pages:
            unit_chunks.append(blocks[page])
            unit_chunks.append("")
            full_chunks.append(blocks[page])
            full_chunks.append("")

        unit_path = units_dir / f"{idx:02d}_{safe_name(unit_label)}_{start}-{end}.md"
        unit_path.write_text(clean_text("\n".join(unit_chunks)), encoding="utf-8")
        unit_files.append(unit_path)
        offset_checks.append(
            {
                "title": unit_label,
                "chosen_start": start,
                "chosen_end": end,
                "source_pdf": str(pdf_path),
                "order_key": item.get("order_key", []),
                "pattern": item.get("pattern", ""),
            }
        )
        source_reports.append(
            {
                "pdf": str(pdf_path),
                "pdf_name": pdf_path.name,
                "sha256": sha256(pdf_path),
                **meta,
                "page_start": start,
                "page_end": end,
            }
        )
        engine_values.append(meta["engine"])
        mode_values.append(meta["mode"])
        offset_values.append(str(meta["offset"]))

    full_md = clean_text("\n".join(full_chunks))
    full_path = book_dir / f"{book_key}.md"
    full_path.write_text(full_md, encoding="utf-8")
    if parts_dir.exists() and not any(parts_dir.rglob("*")):
        shutil.rmtree(parts_dir)

    report = {
        "subject": subject,
        "pdf": ";".join(str(path) for path in pdf_paths),
        "pdf_name": f"{book_key}.pdf-group",
        "sha256": combined_sha256(pdf_paths),
        "engine": "+".join(sorted(set(engine_values))),
        "mode": "+".join(sorted(set(mode_values))),
        "offset": ",".join(offset_values),
        "analysis": {
            "yellow_auto_group": True,
            "scope": candidate.get("scope"),
            "patterns": candidate.get("patterns", []),
            "source_reports": source_reports,
        },
        "garbled_retry": any(r.get("garbled_retry") for r in source_reports),
        "unit_count": len(unit_files),
        "full_markdown": str(full_path),
        "unit_files": [str(path) for path in unit_files],
        "offset_checks": offset_checks,
    }
    report_path = reports_dir / f"local_yellow_{subject}_{book_key}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert safe yellow split-source PDF groups.")
    parser.add_argument("--input", default="../textbook", help="Local textbook root.")
    parser.add_argument("--output", default="../textbook/output_md", help="Markdown output root.")
    parser.add_argument("--reports", default="../textbook/_conversion_reports", help="Report output folder.")
    parser.add_argument(
        "--grouping",
        default="../textbook/_conversion_reports/yellow_grouping_report.json",
        help="Yellow grouping JSON.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print planned conversion count.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for smoke runs.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing full Markdown output.")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    reports_dir = Path(args.reports).expanduser().resolve()
    grouping_path = Path(args.grouping).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    candidates = load_auto_candidates(grouping_path, input_dir)
    skipped_existing = []
    planned = []
    for candidate in candidates:
        full_path = candidate_output_path(output_dir, candidate)
        if full_path.exists() and not args.force:
            skipped_existing.append(
                {
                    "scope": candidate.get("scope"),
                    "book_key": candidate["book_key"],
                    "pdf_count": len(candidate.get("pdfs", [])),
                    "full_markdown": str(full_path),
                }
            )
        else:
            planned.append(candidate)

    if args.limit:
        planned = planned[: args.limit]

    print(f"yellow_auto_candidates {len(candidates)}", flush=True)
    print(f"skip_existing_full_output {len(skipped_existing)}", flush=True)
    print(f"planned_groups {len(planned)}", flush=True)
    if args.dry_run:
        for candidate in planned[:80]:
            print(f"plan {candidate['scope']} / {candidate['book_key']} ({len(candidate['pdfs'])} pdf)", flush=True)
        return

    (reports_dir / "environment.json").write_text(json.dumps(version_info(), ensure_ascii=False, indent=2), encoding="utf-8")
    completed = []
    failed = []
    for idx, candidate in enumerate(planned, start=1):
        label = f"{candidate['scope']} / {candidate['book_key']}"
        print(f"convert yellow-auto {idx}/{len(planned)} {label} ({len(candidate['pdfs'])} pdf)", flush=True)
        try:
            report = convert_auto_candidate(input_dir, output_dir, reports_dir, candidate)
            completed.append(report)
            print(f"done {report['pdf_name']}: {report['engine']} units={report['unit_count']}", flush=True)
        except Exception as exc:
            failed.append({"label": label, "type": type(exc).__name__, "message": str(exc)})
            print(f"fail {label}: {type(exc).__name__}: {exc}", flush=True)

    all_reports = load_existing_reports(reports_dir)
    write_manifest(all_reports, reports_dir)
    summary = {
        "auto_candidates": len(candidates),
        "skipped_existing_full_output": len(skipped_existing),
        "planned_groups": len(planned),
        "completed_groups": len(completed),
        "failed_groups": len(failed),
        "skipped": skipped_existing,
        "failed": failed,
    }
    summary_path = reports_dir / "yellow_auto_conversion_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
