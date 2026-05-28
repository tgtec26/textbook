#!/usr/bin/env python3
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import fitz

from convert_local import conversion_groups, donga_middle_science_part, list_pdfs, subject_for
from process_drive_textbooks import likely_page_number


SKIP_DIRS = {
    ".git",
    ".venv",
    ".claude",
    ".codex",
    ".serena",
    "__pycache__",
    "output_md",
    "_conversion_reports",
    "tmp_downloads",
}


def visible_local_pdfs(input_dir: Path) -> list[Path]:
    pdfs = []
    for path in list_pdfs(input_dir):
        rel_parts = path.relative_to(input_dir).parts
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel_parts):
            continue
        pdfs.append(path)
    return pdfs


def footer_numbers(page, *, max_lines: int = 80) -> list[int]:
    h = page.rect.height
    nums = []
    data = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
    seen = 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            if seen >= max_lines:
                return nums
            seen += 1
            x0, y0, x1, y1 = line["bbox"]
            if y0 < h * 0.76:
                continue
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            n = likely_page_number(text)
            if n is not None:
                nums.append(n)
    return nums


def inspect_pdf(pdf_path: Path, sample_pages: int) -> dict:
    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        indices = list(range(min(page_count, sample_pages)))
        if page_count > sample_pages:
            indices.extend(range(max(sample_pages, page_count - 2), page_count))
        indices = sorted(set(indices))
        ratios = []
        footer_samples = []
        text_chars = 0
        for index in indices:
            page = doc[index]
            ratios.append(page.rect.width / page.rect.height)
            text = page.get_text("text", flags=fitz.TEXTFLAGS_TEXT)
            text_chars += len(re.sub(r"\s+", "", text))
            footer_samples.extend({"physical": index + 1, "printed": n} for n in footer_numbers(page))

    mode = "two-up" if ratios and sum(1 for ratio in ratios if ratio > 1.25) >= max(1, len(ratios) // 2) else "one-up"
    offsets = []
    for sample in footer_samples:
        if mode == "two-up":
            offsets.append(sample["printed"] - (sample["physical"] * 2))
        else:
            offsets.append(sample["printed"] - sample["physical"])
    offset = Counter(offsets).most_common(1)[0][0] if offsets else None
    return {
        "page_count": page_count,
        "mode": mode,
        "ratios": [round(ratio, 3) for ratio in ratios[:4]],
        "text_chars_sample": text_chars,
        "footer_sample_count": len(footer_samples),
        "offset_sample": offset,
    }


def filename_kind(pdf_path: Path) -> str:
    name = pdf_path.name
    if re.search(r"_[0-9]+(?:-[0-9]+)+_교과서\.pdf$", name):
        return "subunit_numeric"
    if re.search(r"_[0-9]+(?:-[0-9]+)?단원_", name):
        return "major_danwon"
    if re.search(r"_[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ](?:-|단원|\.)", name):
        return "major_roman"
    return "single_or_unknown"


def group_label(input_dir: Path, group: list[Path]) -> str:
    part = donga_middle_science_part(group[0])
    if part and len(group) > 1:
        return f"{subject_for(input_dir, group[0])}/{part['book_stem']}"
    first = group[0]
    return f"{subject_for(input_dir, first)}/{first.stem}"


def risk_for_group(records: list[dict]) -> tuple[str, list[str]]:
    reasons = []
    if any(record.get("open_error") for record in records):
        reasons.append("open_error")
    if any(record["inspect"].get("text_chars_sample", 0) == 0 for record in records if "inspect" in record):
        reasons.append("no_text_sample")
    if any(record["inspect"].get("footer_sample_count", 0) == 0 for record in records if "inspect" in record):
        reasons.append("no_footer_sample")
    if len(records) > 1:
        reasons.append("multi_pdf_group")
    if any(record["kind"] in {"subunit_numeric", "major_danwon", "major_roman"} for record in records):
        reasons.append("split_source_pdf")
    if any(record["inspect"].get("mode") == "two-up" for record in records if "inspect" in record):
        reasons.append("two_up_pdf")

    if "open_error" in reasons or "no_text_sample" in reasons:
        return "red", reasons
    if reasons:
        return "yellow", reasons
    return "green", []


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# Textbook PDF Preflight Audit",
        "",
        f"- Input: `{report['input_dir']}`",
        f"- PDFs: {report['summary']['pdf_count']}",
        f"- Groups: {report['summary']['group_count']}",
        f"- Runtime seconds: {report['summary']['elapsed_seconds']}",
        "",
        "## Risk Summary",
        "",
    ]
    for risk, count in report["summary"]["risk_counts"].items():
        lines.append(f"- {risk}: {count}")
    lines.extend(["", "## Mode Summary", ""])
    for mode, count in report["summary"]["mode_counts"].items():
        lines.append(f"- {mode}: {count}")
    lines.extend(["", "## Filename Kind Summary", ""])
    for kind, count in report["summary"]["kind_counts"].items():
        lines.append(f"- {kind}: {count}")
    lines.extend(["", "## Red Groups", ""])
    red_groups = [group for group in report["groups"] if group["risk"] == "red"]
    if not red_groups:
        lines.append("- none")
    for group in red_groups[:80]:
        lines.append(f"- `{group['label']}`: {', '.join(group['reasons'])}")
    lines.extend(["", "## Yellow Sample", ""])
    for group in [group for group in report["groups"] if group["risk"] == "yellow"][:80]:
        lines.append(f"- `{group['label']}`: {', '.join(group['reasons'])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit local textbook PDFs before conversion.")
    parser.add_argument("--input", default="../textbook", help="Local textbook root.")
    parser.add_argument("--reports", default="../textbook/_conversion_reports", help="Report output folder.")
    parser.add_argument("--sample-pages", type=int, default=6, help="Number of leading pages to inspect per PDF.")
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum number of PDFs for smoke tests.")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    reports_dir = Path(args.reports).expanduser().resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    pdfs = visible_local_pdfs(input_dir)
    if args.limit:
        pdfs = pdfs[: args.limit]
    groups = conversion_groups(input_dir, pdfs)
    records_by_path = {}
    for idx, pdf_path in enumerate(pdfs, start=1):
        record = {
            "path": str(pdf_path),
            "relative_path": str(pdf_path.relative_to(input_dir)),
            "name": pdf_path.name,
            "kind": filename_kind(pdf_path),
            "symlink": pdf_path.is_symlink(),
        }
        try:
            record["inspect"] = inspect_pdf(pdf_path, args.sample_pages)
        except Exception as exc:
            record["open_error"] = {"type": type(exc).__name__, "message": str(exc)}
        records_by_path[pdf_path] = record
        if idx % 100 == 0:
            print(f"audited {idx}/{len(pdfs)}", flush=True)

    group_reports = []
    for group in groups:
        records = [records_by_path[path] for path in group]
        risk, reasons = risk_for_group(records)
        group_reports.append(
            {
                "label": group_label(input_dir, group),
                "risk": risk,
                "reasons": reasons,
                "pdf_count": len(group),
                "pdfs": records,
            }
        )

    risk_counts = Counter(group["risk"] for group in group_reports)
    mode_counts = Counter(
        record["inspect"]["mode"] for record in records_by_path.values() if "inspect" in record
    )
    kind_counts = Counter(record["kind"] for record in records_by_path.values())
    report = {
        "input_dir": str(input_dir),
        "summary": {
            "pdf_count": len(pdfs),
            "group_count": len(groups),
            "risk_counts": dict(sorted(risk_counts.items())),
            "mode_counts": dict(sorted(mode_counts.items())),
            "kind_counts": dict(sorted(kind_counts.items())),
            "elapsed_seconds": round(time.time() - started, 1),
        },
        "groups": group_reports,
    }

    json_path = reports_dir / "preflight_audit.json"
    md_path = reports_dir / "preflight_audit.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"json {json_path}")
    print(f"markdown {md_path}")


if __name__ == "__main__":
    main()
