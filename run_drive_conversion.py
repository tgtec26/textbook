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
    logical_page_number,
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
    page_items: dict[int, list[dict]] = {}
    chunk_size = 40
    doc = fitz.open(pdf_path)

    def run_range(start: int, end: int) -> list[dict]:
        chunk_dir = out_dir / f"chunk_{start:04d}_{end:04d}"
        shutil.rmtree(chunk_dir, ignore_errors=True)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        cmd = (
            f'export PATH="{JAVA_BIN}:$PATH"; '
            f'. "{ODL_VENV}"; '
            f'opendataloader-pdf "{pdf_path}" -o "{chunk_dir}" -f json '
            f'--pages {start}-{end} '
            f'--image-output off --quiet'
        )
        proc = subprocess.run(cmd, shell=True, executable="/bin/zsh", timeout=1800, text=True, capture_output=True)
        if proc.returncode != 0:
            if start == end:
                fallback = clean_text(doc[start - 1].get_text("text"))
                return [
                    {
                        "type": "paragraph",
                        "page number": start,
                        "bounding box": [0, 0, doc[start - 1].rect.width, doc[start - 1].rect.height],
                        "content": f"<!-- OpenDataLoader failed on this page; PyMuPDF fallback used. -->\n{fallback}",
                    }
                ]
            mid = (start + end) // 2
            return run_range(start, mid) + run_range(mid + 1, end)
        files = sorted(chunk_dir.glob("*.json"))
        if not files:
            raise RuntimeError(f"OpenDataLoader output missing: {pdf_path} pages {start}-{end}")
        data = json.loads(files[0].read_text(encoding="utf-8"))
        return data.get("kids", [])

    for start in range(1, page_count + 1, chunk_size):
        end = min(page_count, start + chunk_size - 1)
        for item in run_range(start, end):
            page_no = int(item.get("page number") or 0)
            if page_no:
                page_items.setdefault(page_no, []).append(item)

    mode, offset, _ = detect_mode_and_offset(pdf_path)
    chunks = [f"# {pdf_path.stem}", "> 변환 기준: OpenDataLoader PDF JSON"]
    for physical in range(1, page_count + 1):
        logical = logical_page_number(physical, 0, mode, offset)
        if logical < 0:
            continue
        body = opendataloader_page_to_md(page_items.get(physical, []), doc[physical - 1].rect, logical)
        if body.strip():
            chunks.append(f"## {logical}쪽")
            chunks.append(body)
    return clean_text("\n".join(chunks))


def opendataloader_page_to_md(items: list[dict], rect, logical_page: int) -> str:
    page_w = rect.width
    page_h = rect.height
    text_items = []
    for item in items:
        content = str(item.get("content") or "").strip()
        bbox = item.get("bounding box")
        if not content or not bbox or len(bbox) != 4:
            continue
        if should_skip_opendataloader_item(content, bbox, page_w, page_h):
            continue
        text_items.append({"content": content, "bbox": [float(v) for v in bbox]})

    side_is_left = logical_page % 2 == 0

    def in_side_zone(item: dict) -> bool:
        x0, _, x1, _ = item["bbox"]
        if side_is_left:
            return x1 <= page_w * 0.31
        return x0 >= page_w * 0.69

    def in_main_zone(item: dict) -> bool:
        x0, _, x1, _ = item["bbox"]
        if side_is_left:
            return x0 >= page_w * 0.29
        return x1 <= page_w * 0.71

    main_refs = [item for item in text_items if in_main_zone(item)]

    def overlaps_main(item: dict) -> bool:
        _, y0, _, y1 = item["bbox"]
        for ref in main_refs:
            _, ry0, _, ry1 = ref["bbox"]
            if min(y1, ry1) - max(y0, ry0) > 2:
                return True
        return False

    main = []
    side = []
    for item in text_items:
        if in_side_zone(item) and overlaps_main(item):
            side.append(item["content"])
        else:
            main.append(item["content"])

    body = main[:]
    if side:
        body.append("### 보조단")
        body.extend(side)
    return "\n".join(body)


def should_skip_opendataloader_item(content: str, bbox: list[float], page_w: float, page_h: float) -> bool:
    compact = re.sub(r"\s+", "", content)
    x0, y0, x1, y1 = bbox
    if not compact:
        return True
    if re.fullmatch(r"\d{2}", compact) and x0 > page_w * 0.85:
        return True
    if y1 < page_h * 0.08 and re.search(r"\b\d{1,3}\b", content):
        return True
    if ".ind" in content or ".indd" in content.lower():
        return True
    if re.fullmatch(r"[,，ㆍ·\s]+", content):
        return True
    return False


def convert_book(pdf_path: Path, book_dir: Path) -> tuple[str, dict]:
    mode, offset, analysis = detect_mode_and_offset(pdf_path)
    broken = has_garbled_text(pdf_path)
    if broken:
        md = convert_with_opendataloader(pdf_path, book_dir / "_opendataloader")
        engine = "OpenDataLoader"
    else:
        md = clean_text(convert_pdf(pdf_path, mode, offset))
        engine = "PyMuPDF"
    md = apply_known_manual_fixes(pdf_path.stem, md)
    return md, {"engine": engine, "mode": mode, "offset": offset, "analysis": analysis, "garbled_retry": broken}


def apply_known_manual_fixes(stem: str, md: str) -> str:
    if stem != "비상_중학교_역사2_이병인_교과서" or "## 54쪽" not in md:
        return md
    replacement = """## 54쪽
새로운 사상의 유행
신라 말에는 불교 종파 중 선종이 크게 유행하였다. 경전 연구를 중요하게 여긴 교종과 달리 선종은 참선 등의 수행으로 누구나 내면의 진리를 발견할 수 있다고 하였다. 중앙의 권위와 귀족의 수탈에서 벗어나고자 하였던 호족과 백성이 선종에 호응하였고, 호족의 후원으로 전국에 선종 사찰이 세워졌다. 또한 깨달음을 얻은 승려를 부처와 같이 여겨 승려의 뼈와 사리를 모시는 승탑을 많이 만들었다.
한편, 선종 승려인 도선은 땅의 생김새와 기운이 인간의 삶에 영향을 미친다는 풍수지리설을 널리 퍼뜨렸다. 풍수지리설은 금성 중심의 인식에서 벗어나 지방의 독자성을 강조하였고, 이는 선종과 함께 지방 호족의 사상적 기반이 되었다.
후삼국의 성립
신라 말 지방에서 일어난 세력 가운데 견훤과 궁예가 각각 나라를 세우면서 한반도는 후삼국으로 나뉘었다. 서남해안을 지키는 군진의 군인이었던 견훤은 완산주(전주)를 도읍으로 하여 후백제를 세웠다(900). 후백제는 오늘날의 전라도, 충청도, 경상도 일부를 차지하고 신라를 위협하며 세력을 다투었다. 중국, 일본 등과도 교류하였다.
한편, 신라의 왕족 출신으로 알려진 궁예가 송악(개성)을 수도로 삼고 후고려(후고구려)를 세웠다(901). 이후 나라 이름을 마진으로 고치고 철원으로 수도를 옮겼으나, 나라 이름을 다시 태봉으로 바꾸었다.
곡성 태안사 적인 선사 탑(전남 곡성)
후삼국의 성립: 후백제와 후고려(후고구려)의 성립으로 신라의 영토는 경상도 일대로 축소되었다.
### 보조단
배운 내용을 확인해요
1. 빈칸에 알맞은 말을 써 보자.
삼국 통일을 이룬 신라는 옛 고구려와 백제 출신에게도 관직을 주었다.
당이 흑수 말갈과 손을 잡고 발해를 압박하자 발해는 장문휴를 보내 산둥 지방을 공격하였다.
2. 다음 초성을 참고하여 설명하는 용어를 써 보자.
호족: 통일 신라 말에 스스로 '성주', '장군'이라 부르며 지방을 실질적으로 다스린 세력
녹읍: 관리가 토지에서 세금을 거둘 수 있는 권리만 가진 통일 신라 시대의 토지 제도
육두품: 골품제를 비판하며 사회를 개혁하고자 하였던 통일 신라의 지배층
해동성국: '바다 동쪽의 융성한 나라'라는 뜻으로, 당에서 전성기를 이룬 발해를 부르던 말
풍수지리설: 도선이 보급하였으며, 땅의 생김새와 기운이 인간의 삶에 영향을 미친다는 사상
3. 배운 내용을 확인해 보자.
통일 이후 신라가 체제를 정비한 목적을 말할 수 있나요?
발해의 통치 제도의 특징을 설명할 수 있나요?
신라 말 사회 혼란의 내용을 정리할 수 있나요?"""
    start = md.index("## 54쪽")
    end = md.find("\n## 55쪽", start)
    if end == -1:
        return md
    return clean_text(md[:start] + replacement + "\n" + md[end:])


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
