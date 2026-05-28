#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from convert_local import convert_group, version_info, write_manifest


def load_green_groups(report_path: Path) -> list[list[Path]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    groups = []
    for group in report.get("groups", []):
        if group.get("risk") != "green":
            continue
        paths = [Path(record["path"]) for record in group.get("pdfs", [])]
        existing = [path for path in paths if path.exists()]
        if existing:
            groups.append(existing)
    return groups


def load_existing_reports(reports_dir: Path) -> list[dict]:
    reports = []
    for path in sorted(reports_dir.glob("local_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "pdf_name" in data:
            reports.append(data)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert only green-risk groups from preflight audit.")
    parser.add_argument("--input", default="../textbook", help="Local textbook root.")
    parser.add_argument("--output", default="../textbook/output_md", help="Markdown output root.")
    parser.add_argument("--reports", default="../textbook/_conversion_reports", help="Report output folder.")
    parser.add_argument("--preflight", default="../textbook/_conversion_reports/preflight_audit.json", help="Preflight audit JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned conversion count.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for smoke runs.")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    reports_dir = Path(args.reports).expanduser().resolve()
    preflight_path = Path(args.preflight).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    groups = load_green_groups(preflight_path)
    if args.limit:
        groups = groups[: args.limit]
    print(f"green_groups {len(groups)}", flush=True)
    print(f"green_pdfs {sum(len(group) for group in groups)}", flush=True)
    if args.dry_run:
        for group in groups[:20]:
            print("plan", ";".join(str(path) for path in group), flush=True)
        return

    (reports_dir / "environment.json").write_text(json.dumps(version_info(), ensure_ascii=False, indent=2), encoding="utf-8")
    completed = []
    failed = []
    for idx, group in enumerate(groups, start=1):
        label = group[0].name if len(group) == 1 else f"{group[0].name} (+{len(group)-1})"
        print(f"convert green {idx}/{len(groups)} {label}", flush=True)
        try:
            report = convert_group(input_dir, output_dir, reports_dir, group)
            completed.append(report)
            print(f"done {report['pdf_name']}: {report['engine']} units={report['unit_count']}", flush=True)
        except Exception as exc:
            failed.append({"paths": [str(path) for path in group], "type": type(exc).__name__, "message": str(exc)})
            print(f"fail {label}: {type(exc).__name__}: {exc}", flush=True)

    all_reports = load_existing_reports(reports_dir)
    write_manifest(all_reports, reports_dir)
    summary = {
        "planned_groups": len(groups),
        "completed_groups": len(completed),
        "failed_groups": len(failed),
        "failed": failed,
    }
    (reports_dir / "green_conversion_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
