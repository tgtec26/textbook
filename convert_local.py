#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import fitz

from run_drive_conversion import clean_text, convert_book, page_blocks, safe_name, split_units


DONGA_MIDDLE_SCIENCE_UNITS = {
    "과학1": [
        "과학과인류의지속가능한삶",
        "생물의구성과다양성",
        "열",
        "물질의상태변화",
        "힘의작용",
        "기체의성질",
        "태양계",
    ],
    "과학2": [
        "물질의특성",
        "지권의변화",
        "빛과파동",
        "물질의구성",
        "식물과에너지",
        "동물과에너지",
        "전기와자기",
        "별과우주",
    ],
}


DONGA_MIDDLE_SCIENCE_TITLES = {
    "과학과인류의지속가능한삶": "과학과 인류의 지속가능한 삶",
    "생물의구성과다양성": "생물의 구성과 다양성",
    "물질의상태변화": "물질의 상태 변화",
    "힘의작용": "힘의 작용",
    "기체의성질": "기체의 성질",
    "물질의특성": "물질의 특성",
    "지권의변화": "지권의 변화",
    "빛과파동": "빛과 파동",
    "물질의구성": "물질의 구성",
    "식물과에너지": "식물과 에너지",
    "동물과에너지": "동물과 에너지",
    "전기와자기": "전기와 자기",
    "별과우주": "별과 우주",
    "열": "열",
    "태양계": "태양계",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_pdfs(input_dir: Path) -> list[Path]:
    seen_realpaths = set()
    pdfs = []
    for path in sorted(input_dir.rglob("*.pdf")):
        if path.is_symlink() or not path.is_file():
            continue
        realpath = path.resolve()
        if realpath in seen_realpaths:
            continue
        seen_realpaths.add(realpath)
        pdfs.append(path)
    return pdfs


def donga_middle_science_part(pdf_path: Path) -> dict | None:
    stem = pdf_path.stem
    match = re.fullmatch(r"동아_중학교_(과학[12])_([^_]+?)(?:_([0-9]+(?:-[0-9]+)+))?_교과서", stem)
    if not match:
        return None
    grade, compact_title, subunit = match.groups()
    order = DONGA_MIDDLE_SCIENCE_UNITS.get(grade, [])
    if compact_title not in order:
        return None
    return {
        "grade": grade,
        "compact_title": compact_title,
        "title": DONGA_MIDDLE_SCIENCE_TITLES.get(compact_title, compact_title),
        "unit_index": order.index(compact_title) + 1,
        "subunit": subunit,
        "book_stem": f"동아_중학교_{grade}_교과서",
    }


def conversion_groups(input_dir: Path, pdfs: list[Path]) -> list[list[Path]]:
    donga_groups: dict[tuple[str, str], dict[str, list[tuple[dict, Path]]]] = {}
    singles = []
    for pdf in pdfs:
        part = donga_middle_science_part(pdf)
        if not part:
            singles.append([pdf])
            continue
        subject = subject_for(input_dir, pdf)
        key = (subject, part["book_stem"])
        donga_groups.setdefault(key, {"major": [], "subunit": []})
        bucket = "subunit" if part["subunit"] else "major"
        donga_groups[key][bucket].append((part, pdf))

    grouped = []
    for _key, buckets in sorted(donga_groups.items()):
        chosen = buckets["major"] or buckets["subunit"]
        chosen = sorted(chosen, key=lambda item: (item[0]["unit_index"], item[0]["subunit"] or ""))
        if buckets["major"]:
            grouped.append([pdf for _part, pdf in chosen])
        else:
            grouped.extend([[pdf] for _part, pdf in chosen])
    return sorted(singles + grouped, key=lambda group: str(group[0].relative_to(input_dir)))


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


def combined_sha256(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()


def convert_donga_middle_science_group(input_dir: Path, output_dir: Path, reports_dir: Path, pdf_paths: list[Path]) -> dict:
    first_part = donga_middle_science_part(pdf_paths[0])
    if first_part is None:
        raise ValueError(f"not a Donga middle school science PDF: {pdf_paths[0]}")
    subject = subject_for(input_dir, pdf_paths[0])
    stem = first_part["book_stem"]
    book_dir = output_dir / subject / stem
    parts_dir = book_dir / "_parts"
    units_dir = book_dir / "units"
    book_dir.mkdir(parents=True, exist_ok=True)
    units_dir.mkdir(parents=True, exist_ok=True)
    for old in units_dir.glob("*.md"):
        old.unlink()

    full_chunks = [f"# {stem}", ""]
    unit_files = []
    offset_checks = []
    source_reports = []
    engine_values = []
    mode_values = []
    offset_values = []

    for pdf_path in sorted(pdf_paths, key=lambda p: donga_middle_science_part(p)["unit_index"]):
        part = donga_middle_science_part(pdf_path)
        part_md, meta = convert_book(pdf_path, parts_dir / pdf_path.stem)
        blocks = page_blocks(part_md)
        pages = sorted(blocks)
        start = pages[0] if pages else 1
        end = pages[-1] if pages else start
        title = part["title"]
        idx = part["unit_index"]

        unit_chunks = [f"# {idx}. {title}", ""]
        for page in pages:
            unit_chunks.append(blocks[page])
            unit_chunks.append("")
            full_chunks.append(blocks[page])
            full_chunks.append("")

        unit_path = units_dir / f"{idx:02d}_{safe_name(title)}_{start}-{end}.md"
        unit_path.write_text(clean_text("\n".join(unit_chunks)), encoding="utf-8")
        unit_files.append(unit_path)
        offset_checks.append({"title": title, "chosen_start": start, "chosen_end": end, "source_pdf": str(pdf_path)})
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
    full_path = book_dir / f"{stem}.md"
    full_path.write_text(full_md, encoding="utf-8")
    if parts_dir.exists() and not any(parts_dir.rglob("*")):
        shutil.rmtree(parts_dir)
    report = {
        "subject": subject,
        "pdf": ";".join(str(p) for p in pdf_paths),
        "pdf_name": f"{stem}.pdf-group",
        "sha256": combined_sha256(pdf_paths),
        "engine": "+".join(sorted(set(engine_values))),
        "mode": "+".join(sorted(set(mode_values))),
        "offset": ",".join(offset_values),
        "analysis": {"grouped_source_pdfs": len(pdf_paths), "source_reports": source_reports},
        "garbled_retry": any(r.get("garbled_retry") for r in source_reports),
        "unit_count": len(unit_files),
        "full_markdown": str(full_path),
        "unit_files": [str(p) for p in unit_files],
        "offset_checks": offset_checks,
    }
    report_path = reports_dir / f"local_{subject}_{stem}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def convert_group(input_dir: Path, output_dir: Path, reports_dir: Path, pdf_paths: list[Path]) -> dict:
    if len(pdf_paths) == 1:
        return convert_one(input_dir, output_dir, reports_dir, pdf_paths[0])
    if donga_middle_science_part(pdf_paths[0]):
        return convert_donga_middle_science_group(input_dir, output_dir, reports_dir, pdf_paths)
    raise ValueError(f"unsupported PDF group: {pdf_paths}")


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
    groups = conversion_groups(input_dir, pdfs)
    if not groups:
        raise SystemExit(f"no PDF files found: {input_dir}")

    (reports_dir / "environment.json").write_text(json.dumps(version_info(), ensure_ascii=False, indent=2), encoding="utf-8")

    reports = []
    started = not bool(args.start_at)
    for group in groups:
        pdf_path = group[0]
        rel = str(pdf_path.relative_to(input_dir))
        marker = f"{subject_for(input_dir, pdf_path)}/{pdf_path.stem}"
        group_marker = ""
        first_part = donga_middle_science_part(pdf_path)
        if first_part and len(group) > 1:
            group_marker = f"{subject_for(input_dir, pdf_path)}/{first_part['book_stem']}"
        if not started:
            if args.start_at in {rel, marker, pdf_path.stem, group_marker}:
                started = True
            else:
                print(f"skip {rel}", flush=True)
                continue

        label = group_marker or marker
        print(f"convert {label} ({len(group)} pdf)", flush=True)
        report = convert_group(input_dir, output_dir, reports_dir, group)
        reports.append(report)
        print(
            f"done {label}: {report['engine']} units={report['unit_count']} sha256={report['sha256'][:12]}",
            flush=True,
        )

        if args.end_at and args.end_at in {rel, marker, pdf_path.stem, group_marker}:
            break

    write_manifest(reports, reports_dir)
    print(f"summary {len(reports)} textbook groups, {sum(r['unit_count'] for r in reports)} Markdown units", flush=True)
    print(f"output {output_dir}", flush=True)
    print(f"reports {reports_dir}", flush=True)


if __name__ == "__main__":
    main()
