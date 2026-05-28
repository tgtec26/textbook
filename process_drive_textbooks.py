#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz


ROOT = Path("drive_work")
DOWNLOADS = ROOT / "pdfs"
OUTPUTS = ROOT / "outputs"
REPORTS = ROOT / "reports"

SUBJECT_FOLDERS = {
    "과학": "1h4FPka7yjKB37bxzrJj11judT36Ua1uK",
    "국어": "1wyUeXXMaedz-c9dZoW30sMRPvvuZkAdC",
    "도덕": "1ZeS7x6SBYw4qHe57dAFHFlZdK3N7AW7O",
    "사회": "13EPqIGq7nDalJjpNZgsq8ZDebVGMyn_8",
    "수학": "1Yk5xRx_lwRHnI2Qhd3SSjKEWCLc7axj4",
    "역사": "1VYlol-860k5hFTDMyruf8igoSlPIX6bC",
    "영어": "1vdjFoPqTDYEpi-0QxVrk3OX5kjZOEDVQ",
}

FOLDER_MIME = "application/vnd.google-apps.folder"
PDF_MIME = "application/pdf"
MD_MIME = "text/markdown"


@dataclass
class DriveItem:
    subject: str
    id: str
    name: str
    mime_type: str
    parents: list[str]
    trashed: bool = False


def run_gws(args: list[str], *, output: Path | None = None, timeout: int = 600) -> dict:
    cmd = ["gws", *args]
    if output:
        cmd += ["--output", str(output)]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"gws failed: {' '.join(cmd)}\n{proc.stderr}\n{proc.stdout}")
    if output:
        return {}
    stdout = proc.stdout.strip()
    if "Using keyring backend:" in stdout:
        stdout = "\n".join(line for line in stdout.splitlines() if not line.startswith("Using keyring backend:")).strip()
    return json.loads(stdout or "{}")


def list_children(parent_id: str) -> list[dict]:
    params = {
        "q": f"'{parent_id}' in parents and trashed=false",
        "fields": "files(id,name,mimeType,parents,trashed,capabilities,size)",
        "pageSize": 100,
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }
    return run_gws(["drive", "files", "list", "--params", json.dumps(params, ensure_ascii=False)]).get("files", [])


def inventory() -> list[DriveItem]:
    out: list[DriveItem] = []
    for subject, folder_id in SUBJECT_FOLDERS.items():
        queue = [folder_id]
        seen = set()
        while queue:
            parent = queue.pop(0)
            if parent in seen:
                continue
            seen.add(parent)
            for item in list_children(parent):
                drive_item = DriveItem(
                    subject=subject,
                    id=item["id"],
                    name=item["name"],
                    mime_type=item["mimeType"],
                    parents=item.get("parents", []),
                    trashed=item.get("trashed", False),
                )
                out.append(drive_item)
                if drive_item.mime_type == FOLDER_MIME:
                    queue.append(drive_item.id)
    return out


def trash_markdown(items: list[DriveItem]) -> list[DriveItem]:
    md_items = [item for item in items if item.mime_type == MD_MIME or item.name.lower().endswith(".md")]
    print(f"trashing markdown files: {len(md_items)}", flush=True)
    for idx, item in enumerate(md_items, start=1):
        print(f"trash {idx}/{len(md_items)} {item.subject}/{item.name}", flush=True)
        params = {"fileId": item.id, "supportsAllDrives": True}
        run_gws(
            [
                "drive",
                "files",
                "update",
                "--params",
                json.dumps(params),
                "--json",
                json.dumps({"trashed": True}),
            ]
        )
    return md_items


def download_pdfs(items: list[DriveItem]) -> list[tuple[DriveItem, Path]]:
    pdfs = [item for item in items if item.mime_type == PDF_MIME or item.name.lower().endswith(".pdf")]
    downloaded = []
    print(f"downloading pdf files: {len(pdfs)}", flush=True)
    for idx, item in enumerate(pdfs, start=1):
        target = DOWNLOADS / item.subject / item.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size < 1024:
            print(f"download {idx}/{len(pdfs)} {item.subject}/{item.name}", flush=True)
            params = {"fileId": item.id, "alt": "media", "supportsAllDrives": True}
            run_gws(["drive", "files", "get", "--params", json.dumps(params)], output=target)
        else:
            print(f"download skip {idx}/{len(pdfs)} {item.subject}/{item.name}", flush=True)
        downloaded.append((item, target))
    return downloaded


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\u0000-\u001f\u007f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def page_lines(page, clip=None):
    data = page.get_text("dict", clip=clip, flags=fitz.TEXTFLAGS_TEXT)
    lines = []
    ox = clip.x0 if clip else 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = clean("".join(span.get("text", "") for span in line.get("spans", [])))
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            size = max((span.get("size", 0) for span in line.get("spans", [])), default=0)
            lines.append({"text": text, "x0": x0 - ox, "y0": y0, "x1": x1 - ox, "y1": y1, "size": size})
    return lines


def likely_page_number(text: str) -> int | None:
    text = clean(text)
    nums = re.findall(r"(?<![A-Za-z0-9])0*([1-9][0-9]{0,2})(?![A-Za-z0-9])", text)
    if not nums:
        return None
    nums_i = [int(n) for n in nums if 1 <= int(n) <= 450]
    return nums_i[0] if nums_i else None


def printed_footer_number(lines, page_h: float) -> int | None:
    candidates = []
    for line in lines:
        if line["y0"] < page_h * 0.82:
            continue
        n = likely_page_number(line["text"])
        if n is not None:
            candidates.append((line["y0"], n, line["text"]))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def detect_mode_and_offset(pdf_path: Path) -> tuple[str, int, dict]:
    doc = fitz.open(pdf_path)
    ratios = [page.rect.width / page.rect.height for page in doc[: min(len(doc), 8)]]
    wide = sum(1 for r in ratios if r > 1.25) >= max(1, len(ratios) // 2)
    mode = "two-up" if wide else "one-up"
    samples = []
    max_page = min(len(doc), 40)
    for idx in range(1, max_page + 1):
        page = doc[idx - 1]
        w, h = page.rect.width, page.rect.height
        if mode == "two-up":
            halves = [fitz.Rect(0, 0, w / 2, h), fitz.Rect(w / 2, 0, w, h)]
            for side, clip in enumerate(halves):
                n = printed_footer_number(page_lines(page, clip), h)
                if n is not None:
                    samples.append((idx, side, n, n - (2 * idx + side)))
        else:
            n = printed_footer_number(page_lines(page), h)
            if n is not None:
                samples.append((idx, 0, n, n - idx))
    if samples:
        offsets = [s[3] for s in samples]
        offset = max(set(offsets), key=offsets.count)
    else:
        offset = -2 if mode == "two-up" else 0
    report = {"page_count": len(doc), "ratios": ratios, "samples": samples[:30]}
    return mode, offset, report


def logical_page_number(physical: int, side: int, mode: str, offset: int) -> int:
    if mode == "two-up":
        return 2 * physical + side + offset
    return physical + offset


def is_noise_line(line: dict) -> bool:
    text = clean(line["text"])
    if len(text) == 1 and "\uac00" <= text <= "\ud7a3":
        return True
    if text.lower().endswith(".indd"):
        return True
    if text.startswith("그림 ") or text.startswith("표 "):
        return True
    return False


def crop_to_md(page, clip=None) -> str:
    h = page.rect.height
    lines = [line for line in page_lines(page, clip) if not is_noise_line(line)]
    body = []
    for line in sorted(lines, key=lambda item: (round(item["y0"] / 3) * 3, item["x0"])):
        text = line["text"]
        if line["y0"] > h * 0.92 and likely_page_number(text) is not None:
            continue
        body.append(text)
    return "\n".join(body)


def crop_textbook_page_to_md(page, clip=None, side: int | None = None) -> str:
    """Return textbook reading order: header, main column, then helper column."""
    h = page.rect.height
    page_w = (clip.x1 - clip.x0) if clip else page.rect.width
    lines = []
    for line in page_lines(page, clip):
        if is_noise_line(line):
            continue
        if line["y0"] > h * 0.92 and likely_page_number(line["text"]) is not None:
            continue
        lines.append(line)

    if side is None:
        body_lines = [line for line in lines if line["y0"] >= h * 0.12]
        left_side = [line for line in body_lines if line["x1"] < page_w * 0.30]
        right_side = [line for line in body_lines if line["x0"] > page_w * 0.70]
        if len(right_side) >= 3 and len(right_side) > len(left_side):
            side = 1
        elif len(left_side) >= 3 and len(left_side) > len(right_side):
            side = 0
        else:
            ordered = sorted(lines, key=lambda item: (round(item["y0"] / 3) * 3, item["x0"]))
            return "\n".join(line["text"] for line in ordered)

    zones = {"header": [], "main": [], "side": []}
    for line in lines:
        if side == 0 and line["x0"] < page_w * 0.28:
            zones["side"].append(line)
        elif side == 1 and line["x1"] > page_w * 0.72:
            zones["side"].append(line)
        elif line["y0"] < h * 0.12:
            zones["header"].append(line)
        else:
            zones["main"].append(line)

    def ordered_text(zone_lines):
        return [
            line["text"]
            for line in sorted(zone_lines, key=lambda item: (round(item["y0"] / 3) * 3, item["x0"]))
        ]

    body = []
    body.extend(ordered_text(zones["header"]))
    body.extend(ordered_text(zones["main"]))
    side_text = ordered_text(zones["side"])
    if side_text:
        body.append("### 보조단")
        body.extend(side_text)
    return "\n".join(body)


def convert_pdf(pdf_path: Path, mode: str, offset: int) -> str:
    doc = fitz.open(pdf_path)
    chunks = [f"# {pdf_path.stem}", f"> 변환 기준: {mode}, offset={offset}"]
    for physical, page in enumerate(doc, start=1):
        w, h = page.rect.width, page.rect.height
        if mode == "two-up":
            clips = [fitz.Rect(0, 0, w / 2, h), fitz.Rect(w / 2, 0, w, h)]
            for side, clip in enumerate(clips):
                logical = logical_page_number(physical, side, mode, offset)
                if logical < 0:
                    continue
                md = crop_textbook_page_to_md(page, clip, side).strip()
                if md:
                    chunks.append(f"## {logical}쪽")
                    chunks.append(md)
        else:
            logical = logical_page_number(physical, 0, mode, offset)
            if logical < 0:
                continue
            md = crop_textbook_page_to_md(page).strip()
            if md:
                chunks.append(f"## {logical}쪽")
                chunks.append(md)
    return "\n".join(chunk for chunk in chunks if chunk.strip()) + "\n"


def toc_pages(full_md: str) -> list[int]:
    hits = []
    for m in re.finditer(r"^## (\d+)쪽$\n(?:(?!^## \d+쪽$).)*?차례", full_md, flags=re.M | re.S):
        hits.append(int(m.group(1)))
    return hits[:8]


def infer_unit_ranges(full_md: str) -> list[tuple[str, int, int]]:
    page_blocks = []
    for m in re.finditer(r"^## (\d+)쪽$\n", full_md, re.M):
        start = m.end()
        next_m = re.search(r"^## \d+쪽$", full_md[start:], re.M)
        end = start + next_m.start() if next_m else len(full_md)
        page_blocks.append((int(m.group(1)), full_md[start:end]))
    unit_starts = []
    roman_pat = re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧIXV]+$")
    for page_no, body in page_blocks:
        lines = [clean(line) for line in body.splitlines() if clean(line)]
        if page_no < 1 or not lines:
            continue
        first = "\n".join(lines[:8])
        has_roman = any(roman_pat.match(line.replace(" ", "")) for line in lines[:8])
        short_title = len(lines[0]) <= 24 and not re.search(r"[.?!]$", lines[0])
        has_sub = sum(1 for line in lines[:12] if re.match(r"^\d+\.", line)) >= 1
        if (has_roman or has_sub) and short_title:
            if page_no >= 8:
                unit_starts.append((page_no, lines[0]))
    # De-dupe starts close together; keep first page.
    filtered = []
    for page_no, title in unit_starts:
        if filtered and page_no - filtered[-1][0] <= 3:
            continue
        filtered.append((page_no, title))
    ranges = []
    for i, (start, title) in enumerate(filtered):
        end = filtered[i + 1][0] - 1 if i + 1 < len(filtered) else page_blocks[-1][0]
        ranges.append((title, start, end))
    return ranges


def split_units(full_md: str, ranges: list[tuple[str, int, int]], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    page_positions = {int(m.group(1)): m.start() for m in re.finditer(r"^## (\d+)쪽$", full_md, re.M)}
    written = []
    for idx, (title, start, end) in enumerate(ranges, start=1):
        if start not in page_positions:
            continue
        end_pos = page_positions.get(end + 1, len(full_md))
        body = full_md[page_positions[start] : end_pos].strip() + "\n"
        safe_title = re.sub(r'[\\/:*?"<>|\\s]+', "_", title).strip("_") or f"unit_{idx}"
        path = out_dir / f"{idx:02d}_{safe_title}_{start}-{end}.md"
        path.write_text(f"# {idx}. {title}\n\n{body}", encoding="utf-8")
        written.append(path)
    return written


def ensure_split_folder(subject_id: str, name: str, existing: dict[str, str]) -> str:
    folder_name = f"{Path(name).stem}_split"
    if folder_name in existing:
        return existing[folder_name]
    params = {"supportsAllDrives": True}
    body = {"name": folder_name, "mimeType": FOLDER_MIME, "parents": [subject_id]}
    created = run_gws(
        [
            "drive",
            "files",
            "create",
            "--params",
            json.dumps(params),
            "--json",
            json.dumps(body, ensure_ascii=False),
        ]
    )
    return created["id"]


def upload_markdown(files: list[Path], folder_id: str) -> list[str]:
    ids = []
    for path in files:
        params = {"supportsAllDrives": True}
        body = {"name": path.name, "parents": [folder_id], "mimeType": MD_MIME}
        created = run_gws(
            [
                "drive",
                "files",
                "create",
                "--params",
                json.dumps(params),
                "--json",
                json.dumps(body, ensure_ascii=False),
                "--upload",
                str(path),
                "--upload-content-type",
                MD_MIME,
            ]
        )
        ids.append(created["id"])
    return ids


def main():
    for path in (DOWNLOADS, OUTPUTS, REPORTS):
        path.mkdir(parents=True, exist_ok=True)
    items = inventory()
    (REPORTS / "inventory.json").write_text(json.dumps([item.__dict__ for item in items], ensure_ascii=False, indent=2), encoding="utf-8")
    trashed = trash_markdown(items)
    (REPORTS / "trashed_markdown.json").write_text(json.dumps([item.__dict__ for item in trashed], ensure_ascii=False, indent=2), encoding="utf-8")

    # Refresh inventory after trashing, so split-folder lookup ignores old files.
    items = inventory()
    downloaded = download_pdfs(items)
    summary = []
    for item, pdf_path in downloaded:
        mode, offset, analysis = detect_mode_and_offset(pdf_path)
        full_md = convert_pdf(pdf_path, mode, offset)
        book_out_dir = OUTPUTS / item.subject / Path(item.name).stem
        book_out_dir.mkdir(parents=True, exist_ok=True)
        full_path = book_out_dir / f"{Path(item.name).stem}.md"
        full_path.write_text(full_md, encoding="utf-8")
        ranges = infer_unit_ranges(full_md)
        if len(ranges) < 2:
            ranges = [(Path(item.name).stem, min(analysis["samples"][0][2], 1) if analysis["samples"] else 1, max(int(m.group(1)) for m in re.finditer(r"^## (\d+)쪽$", full_md, re.M)))]
        unit_files = split_units(full_md, ranges, book_out_dir / "units")

        subject_folders = {x.name: x.id for x in items if x.subject == item.subject and x.mime_type == FOLDER_MIME and item.id in x.parents or False}
        # Existing split folders are direct children of the subject folder.
        direct_folders = {x.name: x.id for x in items if x.subject == item.subject and x.mime_type == FOLDER_MIME and SUBJECT_FOLDERS[item.subject] in x.parents}
        split_folder_id = ensure_split_folder(SUBJECT_FOLDERS[item.subject], item.name, direct_folders)
        uploaded = upload_markdown(unit_files, split_folder_id)

        validation_pages = sorted({p for _, start, end in ranges for p in range(max(1, start - 5), start + 6)})
        previews = {}
        for p in validation_pages:
            marker = f"## {p}쪽"
            pos = full_md.find(marker)
            if pos >= 0:
                previews[p] = "\n".join(full_md[pos:].splitlines()[:8])
        book_report = {
            "subject": item.subject,
            "pdf": item.name,
            "mode": mode,
            "offset": offset,
            "analysis": analysis,
            "toc_pages": toc_pages(full_md),
            "ranges": ranges,
            "unit_files": [str(p) for p in unit_files],
            "uploaded_ids": uploaded,
            "validation_previews": previews,
        }
        (REPORTS / f"{item.subject}_{Path(item.name).stem}.json").write_text(json.dumps(book_report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.append(book_report)
        print(f"done {item.subject}/{item.name}: {mode} offset={offset} units={len(unit_files)} uploaded={len(uploaded)}")
    (REPORTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
