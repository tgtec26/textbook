#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import fitz

from process_drive_textbooks import (
    MD_MIME,
    OUTPUTS,
    REPORTS,
    SUBJECT_FOLDERS,
    DriveItem,
    convert_pdf,
    detect_mode_and_offset,
    inventory,
    run_gws,
    trash_markdown,
)


ROOT = Path("drive_work")
PDF_DIR = ROOT / "pdfs"
ODL_VENV = Path(".venv-opendataloader/bin/activate")
JAVA_BIN = Path("/opt/homebrew/opt/openjdk/bin")


UNIT_CONFIG = {
    "미래엔_중학교_과학1_김태일_교과서": [
        ("과학과 인류의 지속가능한 삶", 14),
        ("생물의 구성과 다양성", 38),
        ("열", 82),
        ("물질의 상태 변화", 116),
        ("힘의 작용", 156),
        ("기체의 성질", 198),
        ("태양계", 228),
    ],
    "미래엔_중학교_과학2_김태일_교과서": [
        ("물질의 특성", 16),
        ("지권의 변화", 56),
        ("빛과 파동", 98),
        ("물질의 구성", 138),
        ("식물과 에너지", 172),
        ("동물과 에너지", 202),
        ("전기와 자기", 244),
        ("별과 우주", 282),
    ],
    "천재_중학교_국어1-1_노미숙_교과서": [
        ("문학과의 만남", 14),
        ("바람직한 언어생활", 68),
        ("세상을 이해하는 힘", 110),
        ("갈등을 넘어", 152),
    ],
    "천재_중학교_국어1-2_노미숙_교과서": [
        ("성찰하며 성장하며", 14),
        ("소통의 열쇠", 72),
        ("단어의 세계", 110),
        ("글에 담긴 세상", 160),
    ],
    "천재_중학교_국어2-1_노미숙_교과서": [
        ("문학을 펼치면", 14),
        ("소통으로 여는 세상", 76),
        ("나와 세상의 연결 고리", 120),
        ("표현의 빛깔", 166),
    ],
    "천재_중학교_국어2-2_노미숙_교과서": [
        ("세상과 만나는 시간", 14),
        ("분석의 즐거움", 74),
        ("탐구하고 성찰하는 언어생활", 118),
        ("다채로운 글의 세계", 170),
    ],
    "천재_중학교_도덕1_김남준_교과서": [
        ("자신과의 관계", 11),
        ("타인과의 관계", 81),
        ("사회 공동체와의 관계", 137),
        ("자연과의 관계", 205),
    ],
    "천재_중학교_도덕2_김남준_교과서": [
        ("자신과의 관계", 11),
        ("타인과의 관계", 63),
        ("사회 공동체와의 관계", 119),
        ("자연과의 관계", 175),
    ],
    "천재_중학교_사회1_허수미_교과서": [
        ("세계화 시대, 지리의 힘", 10),
        ("아시아", 30),
        ("유럽", 52),
        ("아프리카", 70),
        ("아메리카", 88),
        ("오세아니아와 극지방", 106),
        ("인간과 사회생활", 122),
        ("다양한 문화의 이해", 138),
        ("민주주의와 시민", 154),
        ("정치과정과 시민 참여", 170),
        ("일상생활과 법", 186),
        ("인권과 기본권", 202),
    ],
    "천재_중학교_사회2_허수미_교과서": [
        ("헌법과 국가기관", 10),
        ("경제생활과 선택", 26),
        ("시장과 가격", 42),
        ("우리나라 경제와 세계화", 58),
        ("국제 사회와 한반도", 74),
        ("사회 변동과 사회문제", 90),
        ("대한민국, 우리가 살아가는 곳", 106),
        ("우리나라의 자연환경과 인간 생활", 122),
        ("중부 지역", 142),
        ("남부 지역", 164),
        ("북부 지역", 182),
        ("지속가능한 세계와 글로컬 시민", 198),
    ],
    "교학사_중학교_수학1_김창동_교과서": [
        ("수와 연산", 13),
        ("문자와 식", 65),
        ("그래프와 비례 관계", 107),
        ("기본 도형과 작도", 145),
        ("평면도형과 입체도형", 191),
        ("자료와 가능성", 243),
    ],
    "교학사_중학교_수학2_김창동_교과서": [
        ("수와 식", 13),
        ("부등식과 연립방정식", 57),
        ("일차함수", 97),
        ("도형의 성질", 145),
        ("도형의 닮음", 193),
        ("경우의 수와 확률", 249),
    ],
    "비상_중학교_역사1_이병인_교과서": [
        ("역사 학습의 기초", 9),
        ("문명의 발생과 고대 세계의 형성", 27),
        ("세계 종교의 확산과 지역 문화의 발전", 67),
        ("지역 세계의 교류와 변화", 109),
        ("제국주의와 국민 국가 건설 운동", 145),
        ("세계 대전과 사회 변동", 185),
        ("현대 세계의 전개와 과제", 217),
    ],
    "비상_중학교_역사2_이병인_교과서": [
        ("국가의 형성과 발전", 9),
        ("통일 신라와 발해", 41),
        ("고려의 성립과 변천", 69),
        ("조선의 성립과 발전", 103),
        ("조선 사회의 변동", 131),
        ("근·현대 사회로의 전환", 159),
    ],
    "천재_중학교_영어1_이상기_교과서": [
        ("Lesson 1 Finding Me", 10),
        ("Lesson 2 I Love My School", 26),
        ("Lesson 3 Let's Go Green!", 42),
        ("Lesson 4 Words of Wisdom", 58),
        ("Lesson 5 Walk into Korea", 76),
        ("Lesson 6 The Beauty of Art", 94),
        ("Lesson 7 Tasty World", 110),
        ("Lesson 8 Living Together", 126),
        ("Special Lesson Into the Job World", 144),
    ],
    "천재_중학교_영어2_이상기_교과서": [
        ("Lesson 1 Enjoy Your Days", 10),
        ("Lesson 2 Living Healthy", 28),
        ("Lesson 3 The World of Sports", 46),
        ("Lesson 4 Animal Wonders", 64),
        ("Lesson 5 Be a Detective!", 84),
        ("Lesson 6 Discovering Heroes", 104),
        ("Lesson 7 Be a Smart Shopper", 124),
        ("Lesson 8 Explore the Night Sky", 142),
        ("Special Lesson You Can Be a Poet!", 160),
    ],
}


def clean_text(text: str) -> str:
    """Apply identical final cleanup to every extraction engine."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\\n", "\n")
    text = re.sub(r"[\u0000-\u0008\u000b-\u001f\u007f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        compact = re.sub(r"\s+", "", line)
        if len(compact) == 1 and "\uac00" <= compact <= "\ud7a3":
            continue
        if ".ind" in line or line.lower().endswith(".indd"):
            continue
        if re.fullmatch(r"[0-9]{1,2}", line) and lines and lines[-1].startswith("## "):
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def page_blocks(md: str) -> dict[int, str]:
    matches = list(re.finditer(r"^##\s+(\d+)쪽\s*$", md, re.M))
    blocks = {}
    for idx, match in enumerate(matches):
        page = int(match.group(1))
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(md)
        blocks[page] = md[start:end].strip()
    return blocks


def has_garbled_text(pdf_path: Path) -> bool:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc[: min(20, len(doc))]:
        text += page.get_text("text")[:3000]
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return True
    allowed = set("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ·•℃①②③④⑤⑥⑦⑧⑨⑩→←↑↓~–—“”‘’…ㆍ※")
    weird = sum(
        1
        for c in chars
        if not ("\uac00" <= c <= "\ud7a3")
        and not c.isascii()
        and not ("\u3130" <= c <= "\u318f")
        and c not in allowed
    )
    return weird / len(chars) > 0.12


def convert_with_opendataloader(pdf_path: Path, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    page_count = len(fitz.open(pdf_path))
    parts = []
    chunk_size = 40
    doc = fitz.open(pdf_path)

    def run_range(start: int, end: int) -> list[str]:
        chunk_dir = out_dir / f"chunk_{start:04d}_{end:04d}"
        shutil.rmtree(chunk_dir, ignore_errors=True)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        cmd = (
            f'export PATH="{JAVA_BIN}:$PATH"; '
            f'. "{ODL_VENV}"; '
            f'opendataloader-pdf "{pdf_path}" -o "{chunk_dir}" -f markdown '
            f'--pages {start}-{end} '
            f'--markdown-page-separator "__PAGE_%page-number%__" --image-output off --quiet'
        )
        proc = subprocess.run(cmd, shell=True, executable="/bin/zsh", timeout=1800, text=True, capture_output=True)
        if proc.returncode != 0:
            if start == end:
                fallback = clean_text(doc[start - 1].get_text("text"))
                return [f"__PAGE_{start}__\n\n<!-- OpenDataLoader failed on this page; PyMuPDF fallback used. -->\n\n{fallback}"]
            mid = (start + end) // 2
            return run_range(start, mid) + run_range(mid + 1, end)
        files = sorted(chunk_dir.glob("*.md"))
        if not files:
            raise RuntimeError(f"OpenDataLoader output missing: {pdf_path} pages {start}-{end}")
        return [files[0].read_text(encoding="utf-8")]

    for start in range(1, page_count + 1, chunk_size):
        end = min(page_count, start + chunk_size - 1)
        parts.extend(run_range(start, end))
    raw = "\n\n".join(parts)
    raw = re.sub(r"__PAGE_(\d+)__", r"\n\n## \1쪽\n\n", raw)
    return clean_text(f"# {pdf_path.stem}\n\n> 변환 기준: OpenDataLoader PDF\n\n{raw}")


def convert_book(pdf_path: Path, book_dir: Path) -> tuple[str, dict]:
    mode, offset, analysis = detect_mode_and_offset(pdf_path)
    broken = has_garbled_text(pdf_path)
    if broken:
        md = convert_with_opendataloader(pdf_path, book_dir / "_opendataloader")
        engine = "OpenDataLoader"
    else:
        md = clean_text(convert_pdf(pdf_path, mode, offset))
        engine = "PyMuPDF"
    return md, {"engine": engine, "mode": mode, "offset": offset, "analysis": analysis, "garbled_retry": broken}


def normalize_key(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def adjusted_ranges(stem: str, md: str) -> tuple[list[tuple[str, int, int]], list[dict]]:
    blocks = page_blocks(md)
    pages = sorted(blocks)
    if not pages:
        return [], []
    configured = UNIT_CONFIG.get(stem)
    if not configured:
        return [(stem, pages[0], pages[-1])], [{"title": stem, "reason": "no_config"}]

    starts = []
    checks = []
    for title, first_sub_page in configured:
        if stem == "비상_중학교_역사2_이병인_교과서" and title == "국가의 형성과 발전":
            starts.append((title, 6, first_sub_page))
            checks.append({"title": title, "toc_first_sub_page": first_sub_page, "chosen_start": 6, "checked_pages": list(range(4, 10)), "manual": "image title page"})
            continue
        title_key = normalize_key(title)
        found = None
        candidates = [p for p in pages if first_sub_page - 5 <= p <= first_sub_page]
        for p in candidates:
            if re.search(r"차례|Contents", blocks[p], flags=re.I):
                continue
            body_key = normalize_key("\n".join(blocks[p].splitlines()[:25]))
            if title_key and title_key in body_key:
                found = p
                break
        if found is None:
            non_toc = [p for p in candidates if not re.search(r"차례|Contents", blocks[p], flags=re.I)]
            found = min(non_toc or candidates, default=first_sub_page)
        starts.append((title, found, first_sub_page))
        checks.append({"title": title, "toc_first_sub_page": first_sub_page, "chosen_start": found, "checked_pages": candidates})

    ranges = []
    for idx, (title, start, _) in enumerate(starts):
        end = starts[idx + 1][1] - 1 if idx + 1 < len(starts) else pages[-1]
        ranges.append((title, start, end))
    return ranges, checks


def safe_name(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:90] or "unit"


def split_units(stem: str, md: str, out_dir: Path) -> tuple[list[Path], list[dict]]:
    blocks = page_blocks(md)
    ranges, checks = adjusted_ranges(stem, md)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()
    written = []
    for idx, (title, start, end) in enumerate(ranges, 1):
        chunks = [f"# {idx}. {title}", ""]
        for p in sorted(blocks):
            if start <= p <= end:
                chunks.append(blocks[p])
                chunks.append("")
        path = out_dir / f"{idx:02d}_{safe_name(title)}_{start}-{end}.md"
        path.write_text(clean_text("\n".join(chunks)), encoding="utf-8")
        written.append(path)
    return written, checks


def ensure_split_folder(subject_id: str, folder_name: str) -> str:
    params = {
        "q": f"'{subject_id}' in parents and name='{folder_name}' and trashed=false",
        "fields": "files(id,name,mimeType)",
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }
    found = run_gws(["drive", "files", "list", "--params", json.dumps(params, ensure_ascii=False)]).get("files", [])
    if found:
        return found[0]["id"]
    body = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [subject_id]}
    created = run_gws(
        [
            "drive",
            "files",
            "create",
            "--params",
            json.dumps({"supportsAllDrives": True}),
            "--json",
            json.dumps(body, ensure_ascii=False),
        ]
    )
    return created["id"]


def upload_markdown(files: list[Path], folder_id: str) -> list[str]:
    ids = []
    for path in files:
        body = {"name": path.name, "parents": [folder_id], "mimeType": MD_MIME}
        created = run_gws(
            [
                "drive",
                "files",
                "create",
                "--params",
                json.dumps({"supportsAllDrives": True}),
                "--json",
                json.dumps(body, ensure_ascii=False),
                "--upload",
                str(path),
                "--upload-content-type",
                MD_MIME,
            ],
            timeout=900,
        )
        ids.append(created["id"])
    return ids


def local_pdf_items() -> list[tuple[DriveItem, Path]]:
    manifest = {}
    for line in Path("drive_file_manifest.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        subject, file_id, name = line.split("\t")
        if name.lower().endswith(".pdf"):
            manifest[(subject, name)] = file_id
    out = []
    for pdf in sorted(PDF_DIR.glob("*/*.pdf")):
        subject = pdf.parent.name
        item = DriveItem(subject=subject, id=manifest.get((subject, pdf.name), ""), name=pdf.name, mime_type="application/pdf", parents=[SUBJECT_FOLDERS[subject]])
        out.append((item, pdf))
    return out


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    if os.environ.get("SKIP_TRASH") == "1":
        print("skip drive markdown trash", flush=True)
    else:
        print("refresh drive inventory", flush=True)
        trashed = trash_markdown(inventory())
        (REPORTS / "trashed_markdown_final.json").write_text(json.dumps([x.__dict__ for x in trashed], ensure_ascii=False, indent=2), encoding="utf-8")

    summary = []
    start_at = os.environ.get("START_AT", "")
    end_at = os.environ.get("END_AT", "")
    started = not bool(start_at)
    for item, pdf_path in local_pdf_items():
        marker = f"{item.subject}/{pdf_path.stem}"
        if not started:
            if marker == start_at:
                started = True
            else:
                print(f"skip {marker}", flush=True)
                continue
        stem = pdf_path.stem
        print(f"convert {item.subject}/{item.name}", flush=True)
        book_dir = OUTPUTS / item.subject / stem
        book_dir.mkdir(parents=True, exist_ok=True)
        full_md, meta = convert_book(pdf_path, book_dir)
        full_path = book_dir / f"{stem}.md"
        full_path.write_text(full_md, encoding="utf-8")
        unit_files, checks = split_units(stem, full_md, book_dir / "units")
        folder_id = ensure_split_folder(SUBJECT_FOLDERS[item.subject], f"{stem}_split")
        uploaded = upload_markdown(unit_files, folder_id)
        report = {
            "subject": item.subject,
            "pdf": item.name,
            **meta,
            "unit_count": len(unit_files),
            "unit_files": [str(p) for p in unit_files],
            "upload_folder_id": folder_id,
            "uploaded_ids": uploaded,
            "offset_checks": checks,
        }
        (REPORTS / f"final_{item.subject}_{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.append(report)
        print(f"done {item.subject}/{stem}: {meta['engine']} units={len(unit_files)} uploaded={len(uploaded)}", flush=True)
        if end_at and marker == end_at:
            break
    (REPORTS / "final_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
