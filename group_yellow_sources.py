#!/usr/bin/env python3
import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROMAN_ORDER = {
    "Ⅰ": 1,
    "Ⅱ": 2,
    "Ⅲ": 3,
    "Ⅳ": 4,
    "Ⅴ": 5,
    "Ⅵ": 6,
    "Ⅶ": 7,
    "Ⅷ": 8,
    "Ⅸ": 9,
    "Ⅹ": 10,
}


def split_number_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value))


def parse_split_identity(name: str) -> dict | None:
    stem = unicodedata.normalize("NFC", Path(name).stem)
    if stem.endswith(".pdf"):
        stem = stem[:-4]

    match = re.fullmatch(r"(?P<book>.+?)_(?P<order>\d+(?:-\d+)?)단원_(?:(?P<author>[^_]+)_)?(?P<tail>교과서|부도)", stem)
    if match:
        author = match.group("author")
        book = match.group("book")
        tail = match.group("tail")
        book_key = f"{book}_{author}_{tail}" if author else f"{book}_{tail}"
        return {
            "book_key": book_key,
            "order_key": split_number_key(match.group("order")),
            "unit_label": f"{match.group('order')}단원",
            "pattern": "numbered_danwon",
        }

    match = re.fullmatch(r"(?P<book>.+?)_(?P<roman>[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])-(?P<sub>\d+)단원_(?P<tail>교과서|부도)", stem)
    if match:
        roman = match.group("roman")
        return {
            "book_key": f"{match.group('book')}_{match.group('tail')}",
            "order_key": (ROMAN_ORDER[roman], int(match.group("sub"))),
            "unit_label": f"{roman}-{match.group('sub')}단원",
            "pattern": "roman_sub_danwon",
        }

    match = re.fullmatch(r"(?P<book>.+?)_(?P<roman>[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])단원_(?P<tail>교과서|부도)", stem)
    if match:
        roman = match.group("roman")
        return {
            "book_key": f"{match.group('book')}_{match.group('tail')}",
            "order_key": (ROMAN_ORDER[roman],),
            "unit_label": f"{roman}단원",
            "pattern": "roman_danwon",
        }

    match = re.fullmatch(r"(?P<book>.+?)_(?P<roman>[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])\.(?P<title>.+?)_(?P<tail>교과서|부도)", stem)
    if match:
        roman = match.group("roman")
        return {
            "book_key": f"{match.group('book')}_{match.group('tail')}",
            "order_key": (ROMAN_ORDER[roman],),
            "unit_label": f"{roman}. {match.group('title')}",
            "pattern": "roman_title",
        }

    match = re.fullmatch(r"(?P<book>.+?)_(?P<title>[^_]+)_(?P<order>\d+(?:-\d+)+)_(?P<tail>교과서|부도)", stem)
    if match:
        return {
            "book_key": f"{match.group('book')}_{match.group('tail')}",
            "order_key": split_number_key(match.group("order")),
            "unit_label": match.group("title"),
            "pattern": "title_numeric_subunit",
        }

    return None


def source_scope(relative_path: str) -> str:
    parts = Path(relative_path).parts
    return "/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:1])


def load_yellow_records(preflight: Path) -> list[dict]:
    report = json.loads(preflight.read_text(encoding="utf-8"))
    records = []
    for group in report.get("groups", []):
        if group.get("risk") != "yellow":
            continue
        for record in group.get("pdfs", []):
            parsed = parse_split_identity(record["name"])
            records.append(
                {
                    "group_label": group["label"],
                    "group_reasons": group.get("reasons", []),
                    "relative_path": record["relative_path"],
                    "path": record["path"],
                    "name": record["name"],
                    "kind": record.get("kind"),
                    "inspect": record.get("inspect", {}),
                    "parsed": parsed,
                }
            )
    return records


def build_candidates(records: list[dict]) -> list[dict]:
    buckets = defaultdict(list)
    unparsed = []
    for record in records:
        parsed = record["parsed"]
        if parsed is None:
            unparsed.append(record)
            continue
        key = (source_scope(record["relative_path"]), parsed["book_key"])
        buckets[key].append(record)

    candidates = []
    for (scope, book_key), items in sorted(buckets.items()):
        items = sorted(items, key=lambda item: item["parsed"]["order_key"])
        patterns = sorted({item["parsed"]["pattern"] for item in items})
        modes = sorted({item["inspect"].get("mode", "unknown") for item in items})
        status = "auto_group_candidate" if len(items) >= 2 else "single_split_source"
        candidates.append(
            {
                "scope": scope,
                "book_key": book_key,
                "status": status,
                "pdf_count": len(items),
                "patterns": patterns,
                "modes": modes,
                "pdfs": [
                    {
                        "relative_path": item["relative_path"],
                        "unit_label": item["parsed"]["unit_label"],
                        "order_key": item["parsed"]["order_key"],
                        "pattern": item["parsed"]["pattern"],
                        "mode": item["inspect"].get("mode"),
                        "offset_sample": item["inspect"].get("offset_sample"),
                    }
                    for item in items
                ],
            }
        )

    for record in unparsed:
        candidates.append(
            {
                "scope": source_scope(record["relative_path"]),
                "book_key": record["name"],
                "status": "needs_manual_review",
                "pdf_count": 1,
                "patterns": [],
                "modes": [record["inspect"].get("mode", "unknown")],
                "pdfs": [
                    {
                        "relative_path": record["relative_path"],
                        "unit_label": "",
                        "order_key": [],
                        "pattern": "",
                        "mode": record["inspect"].get("mode"),
                        "offset_sample": record["inspect"].get("offset_sample"),
                    }
                ],
            }
        )
    return candidates


def write_markdown(summary: dict, candidates: list[dict], path: Path) -> None:
    lines = [
        "# Yellow Source Grouping Report",
        "",
        f"- Yellow PDFs: {summary['yellow_pdf_count']}",
        f"- Candidate groups: {summary['candidate_count']}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in summary["status_counts"].items():
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Auto Group Candidates", ""])
    for candidate in [item for item in candidates if item["status"] == "auto_group_candidate"][:120]:
        lines.append(f"- `{candidate['scope']} / {candidate['book_key']}`: {candidate['pdf_count']} PDFs, {', '.join(candidate['patterns'])}")

    lines.extend(["", "## Manual Review Sample", ""])
    for candidate in [item for item in candidates if item["status"] == "needs_manual_review"][:120]:
        lines.append(f"- `{candidate['scope']} / {candidate['book_key']}`")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Group yellow-risk split source PDFs before conversion.")
    parser.add_argument("--preflight", default="../textbook/_conversion_reports/preflight_audit.json")
    parser.add_argument("--reports", default="../textbook/_conversion_reports")
    args = parser.parse_args()

    preflight = Path(args.preflight).expanduser().resolve()
    reports = Path(args.reports).expanduser().resolve()
    reports.mkdir(parents=True, exist_ok=True)

    records = load_yellow_records(preflight)
    candidates = build_candidates(records)
    status_counts = Counter(candidate["status"] for candidate in candidates)
    summary = {
        "yellow_pdf_count": len(records),
        "candidate_count": len(candidates),
        "status_counts": dict(sorted(status_counts.items())),
    }
    payload = {"summary": summary, "candidates": candidates}

    json_path = reports / "yellow_grouping_report.json"
    md_path = reports / "yellow_grouping_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, candidates, md_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json {json_path}")
    print(f"markdown {md_path}")


if __name__ == "__main__":
    main()
