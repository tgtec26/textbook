#!/usr/bin/env python3
import argparse
import re
import unicodedata
from pathlib import Path

import fitz


CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f]")
SPACE_RE = re.compile(r"[ \t]+")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = CONTROL_RE.sub("", text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def line_text(line: dict) -> str:
    return clean_text("".join(span.get("text", "") for span in line.get("spans", [])))


def is_footer(text: str, y0: float, page_h: float) -> bool:
    if y0 < page_h - 58:
        return False
    if re.fullmatch(r"\d{1,3}", text):
        return True
    if re.search(r"\b\d{1,3}\s*$", text) and ("Ⅵ" in text or "쪽" in text or "." in text):
        return True
    if re.search(r"^\d{1,3}\s+", text) and ("Ⅵ" in text or "쪽" in text):
        return True
    return False


def extract_half_lines(page, side: str):
    width = page.rect.width
    height = page.rect.height
    mid = width / 2
    x0, x1 = (0, mid) if side == "left" else (mid, width)
    data = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
    out = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = line_text(line)
            if not text:
                continue
            lx0, ly0, lx1, ly1 = line["bbox"]
            cx = (lx0 + lx1) / 2
            if cx < x0 or cx >= x1:
                continue
            local_x0 = lx0 - x0
            local_x1 = lx1 - x0
            if is_footer(text, ly0, height):
                continue
            if "indd" in text and re.search(r"\d{4}\.", text):
                continue
            out.append(
                {
                    "text": text,
                    "x0": local_x0,
                    "x1": local_x1,
                    "cx": (local_x0 + local_x1) / 2,
                    "y0": ly0,
                    "y1": ly1,
                    "size": max((span.get("size", 0) for span in line.get("spans", [])), default=0),
                }
            )
    return out, mid, height


def is_graphic_text(line: dict, side: str, zone_name: str, half_w: float) -> bool:
    text = line["text"]
    compact = re.sub(r"\s+", "", text)
    short = len(compact) <= 8
    small = line.get("size", 0) <= 8.7

    if text in {"증강 현실", "실험 영상"}:
        return True
    if text.startswith("그림 "):
        return True
    if side == "left" and zone_name == "main" and line["y0"] > 640 and text in {"소화계의 구조와", "기능"}:
        return True

    if zone_name == "header" and small and short:
        if side == "left" and half_w * 0.30 <= line["cx"] <= half_w * 0.75 and line["y0"] > 105:
            return True
        if side == "right" and line["y0"] > 105:
            return True

    if zone_name == "side" and small and short and line["y0"] > 330:
        return True
    if side == "right" and zone_name == "side" and 320 < line["y0"] < 650:
        return True

    return False


def classify(line: dict, side: str, half_w: float) -> str:
    # Textbook pages use one full-width header area, then main text plus an outer helper column.
    if line["y0"] < 185:
        return "header"
    if side == "left":
        return "side" if line["cx"] < half_w * 0.42 else "main"
    return "side" if line["cx"] > half_w * 0.72 else "main"


def sort_lines(lines):
    return sorted(lines, key=lambda item: (round(item["y0"] / 4) * 4, item["x0"]))


def starts_new_paragraph(text: str) -> bool:
    return bool(
        re.match(
            r"^(\d+\.|[①-⑳]|[가-하]\)|\([가-하0-9]+\)|[•\-]|목표|준비물|과정|결과|정리|탐구|자료|그림|표)",
            text,
        )
    )


def is_single_korean_character(text: str) -> bool:
    text = text.strip()
    return len(text) == 1 and "\uac00" <= text <= "\ud7a3"


def lines_to_markdown(lines):
    lines = sort_lines(lines)
    paragraphs = []
    current = []
    prev = None

    for item in lines:
        text = item["text"]
        if is_single_korean_character(text):
            continue
        gap = 999 if prev is None else item["y0"] - prev["y1"]
        far_x = False if prev is None else abs(item["x0"] - prev["x0"]) > 85
        new_para = (
            prev is None
            or starts_new_paragraph(text)
            or gap > 14
            or far_x
            or len(text) <= 8
        )
        if new_para and current:
            paragraphs.append(" ".join(current))
            current = []
        current.append(text)
        prev = item

    if current:
        paragraphs.append(" ".join(current))

    cleaned = []
    for para in paragraphs:
        para = clean_text(para)
        para = re.sub(r"\s+([,.;:!?])", r"\1", para)
        if para:
            cleaned.append(para)
    return "\n".join(cleaned)


def page_number(physical_page_one_based: int, side: str, offset: int) -> int:
    return 2 * physical_page_one_based + offset + (0 if side == "left" else 1)


def convert(pdf_path: Path, output_path: Path, offset: int, start_physical: int, end_physical: int):
    doc = fitz.open(pdf_path)
    end_physical = min(end_physical or len(doc), len(doc))
    chunks = [
        f"# {pdf_path.stem}",
        "",
        f"> 변환 기준: 물리쪽 {start_physical}-{end_physical}, 교과서쪽 = 2 * 물리쪽 + {offset} (오른쪽은 +1)",
        "",
    ]

    for physical in range(start_physical, end_physical + 1):
        page = doc[physical - 1]
        for side in ("left", "right"):
            logical = page_number(physical, side, offset)
            lines, half_w, _ = extract_half_lines(page, side)
            zones = {"header": [], "main": [], "side": []}
            for line in lines:
                zone_name = classify(line, side, half_w)
                if is_graphic_text(line, side, zone_name, half_w):
                    continue
                zones[zone_name].append(line)

            chunks.append(f"## {logical}쪽")
            for zone_name in ("header", "main", "side"):
                md = lines_to_markdown(zones[zone_name])
                if md:
                    if zone_name == "side":
                        chunks.append("### 보조단")
                    chunks.append(md)

    compact_chunks = [chunk for chunk in chunks if chunk.strip()]
    output_path.write_text("\n".join(compact_chunks).rstrip() + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Convert two-up Korean textbook PDF to Markdown.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("textbook.md"))
    parser.add_argument("--offset", type=int, default=-2)
    parser.add_argument("--start-physical", type=int, default=1)
    parser.add_argument("--end-physical", type=int, default=0)
    args = parser.parse_args()
    convert(args.pdf, args.output, args.offset, args.start_physical, args.end_physical)


if __name__ == "__main__":
    main()
