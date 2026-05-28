#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from convert_green_from_preflight import load_existing_reports
from convert_local import (
    conversion_groups,
    convert_group,
    donga_middle_science_part,
    subject_for,
    version_info,
    write_manifest,
)


SKIP_NAME_TOKENS = ("부도", "목록")


def gather_candidate_paths(grouping_path: Path, input_dir: Path) -> tuple[list[Path], dict]:
    report = json.loads(grouping_path.read_text(encoding="utf-8"))
    paths = []
    skipped = {"missing": 0, "atlas_or_catalog": 0}
    for candidate in report.get("candidates", []):
        if candidate.get("status") != "needs_manual_review":
            continue
        for item in candidate.get("pdfs", []):
            path = input_dir / item["relative_path"]
            if not path.exists():
                skipped["missing"] += 1
                continue
            if any(token in path.name for token in SKIP_NAME_TOKENS):
                skipped["atlas_or_catalog"] += 1
                continue
            paths.append(path)
    return paths, skipped


def group_book_stem(group: list[Path]) -> str:
    first = group[0]
    part = donga_middle_science_part(first)
    if part and len(group) > 1:
        return part["book_stem"]
    return first.stem


def group_output_path(input_dir: Path, output_dir: Path, group: list[Path]) -> Path:
    subject = subject_for(input_dir, group[0])
    stem = group_book_stem(group)
    return output_dir / subject / stem / f"{stem}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert standalone yellow PDFs left in manual review.")
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
    parser.add_argument("--force", action="store_true", help="Reconvert even if output already exists.")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    reports_dir = Path(args.reports).expanduser().resolve()
    grouping_path = Path(args.grouping).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    paths, skipped = gather_candidate_paths(grouping_path, input_dir)
    groups = conversion_groups(input_dir, paths)

    planned = []
    skip_existing = 0
    for group in groups:
        if group_output_path(input_dir, output_dir, group).exists() and not args.force:
            skip_existing += 1
            continue
        planned.append(group)
    if args.limit:
        planned = planned[: args.limit]

    print(f"candidate_pdfs {len(paths)}", flush=True)
    print(f"groups {len(groups)}", flush=True)
    print(f"skip_missing {skipped['missing']}", flush=True)
    print(f"skip_atlas_or_catalog {skipped['atlas_or_catalog']}", flush=True)
    print(f"skip_existing_output {skip_existing}", flush=True)
    print(f"planned_groups {len(planned)}", flush=True)
    if args.dry_run:
        for group in planned[:120]:
            stem = group_book_stem(group)
            suffix = f" (+{len(group) - 1} merged)" if len(group) > 1 else ""
            print(f"plan {subject_for(input_dir, group[0])}/{stem}{suffix}", flush=True)
        return

    (reports_dir / "environment.json").write_text(json.dumps(version_info(), ensure_ascii=False, indent=2), encoding="utf-8")
    completed = []
    failed = []
    for idx, group in enumerate(planned, start=1):
        label = f"{subject_for(input_dir, group[0])}/{group_book_stem(group)}"
        print(f"convert single {idx}/{len(planned)} {label} ({len(group)} pdf)", flush=True)
        try:
            report = convert_group(input_dir, output_dir, reports_dir, group)
            completed.append(report)
            print(f"done {report['pdf_name']}: {report['engine']} units={report['unit_count']}", flush=True)
        except Exception as exc:
            failed.append({"paths": [str(p) for p in group], "type": type(exc).__name__, "message": str(exc)})
            print(f"fail {label}: {type(exc).__name__}: {exc}", flush=True)

    all_reports = load_existing_reports(reports_dir)
    write_manifest(all_reports, reports_dir)
    summary = {
        "candidate_pdfs": len(paths),
        "groups": len(groups),
        "planned_groups": len(planned),
        "completed_groups": len(completed),
        "failed_groups": len(failed),
        "skipped": {**skipped, "existing_output": skip_existing},
        "failed_detail": failed,
    }
    (reports_dir / "manual_singles_conversion_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
