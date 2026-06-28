#!/usr/bin/env python3
"""2022 개정 고등학교 교육과정(별책4) PDF → 과목별 Markdown 변환.

- 본문: get_text("dict") 줄 단위 + 표 영역(find_tables bbox) 좌표 제외 → 구조 마커를
  Markdown 으로 매핑. 러닝헤더/페이지번호 제거.
- '가. 내용 체계'의 2D 표: 페이지에 걸친 표를 병합해 Markdown 표로 재구성하고,
  표 셀 텍스트가 본문에 섞이지 않도록 bbox 안의 줄은 본문에서 제외한다.
"""
import re
import sys
import fitz

PDF = "2022_개정_고등학교_교육과정_별책4_수정.pdf"

HEADER_FIRST = {"고등학교 교육과정", "과학과"}
CODE_RE = re.compile(r"^\[\d{2}[가-힣]+\d*[-–][\d∼~]")
NUM_SEC_RE = re.compile(r"^\d+\.\s")
KOR_SUB_RE = re.compile(r"^(가\.\s성격|나\.\s목표|가\.\s내용\s*체계|나\.\s성취기준|가\.\s교수|나\.\s평가)")
AREA_PAREN_RE = re.compile(r"^\(\d+\)\s")
SUBHEAD_PAREN_RE = re.compile(r"^\([가-하]\)\s")
ANGLE_RE = re.compile(r"^<([^>]+)>$")
BULLET_RE = re.compile(r"^[•·]\s?")


def join_para(buf):
    return re.sub(r"[ \t]{2,}", " ", "".join(buf)).strip()


def classify(s):
    s = s.strip()
    if not s:
        return "BLANK"
    if ANGLE_RE.match(s):
        return "ANGLE"
    if NUM_SEC_RE.match(s):
        return "NUMSEC"
    if KOR_SUB_RE.match(s):
        return "KORSUB"
    if SUBHEAD_PAREN_RE.match(s):
        return "SUBHEAD"
    if CODE_RE.match(s):
        return "CODE"
    if BULLET_RE.match(s):
        return "BULLET"
    if AREA_PAREN_RE.match(s):
        return "PAREN"
    return "CONT"


# ---------- 내용 체계 표 ----------
def _clean_cell(c):
    return re.sub(r"\s+", " ", c.replace("\n", " ")).strip() if c else ""


def _split_core_bullets(core):
    """핵심 아이디어 셀을 항목으로 분리. 항목은 '다.'/'.' 로 끝나므로
    마침표 뒤의 ⋅ 에서만 분리한다('산화⋅환원' 같은 중점은 보존)."""
    parts = re.split(r"(?<=\.)\s*⋅", core)
    return [p.lstrip("⋅ ").strip() for p in parts if p.strip()]


def render_content_table(rows):
    core = None
    data = []
    for row in rows:
        cells = [_clean_cell(c) for c in row]
        first = cells[0]
        last = cells[-1]
        if first.startswith("핵심 아이디어"):
            core = last
            continue
        if first.startswith("구분") or (last == "내용 요소"):
            continue  # 헤더 행
        data.append(cells)

    out = []
    if core:
        out += ["**핵심 아이디어**", ""]
        out += [f"- {b}" for b in _split_core_bullets(core)]
        out.append("")
    out += ["| 범주 | 영역 | 내용 요소 |", "| --- | --- | --- |"]
    for cells in data:
        if len(cells) >= 3:
            cat, area, content = cells[0], cells[1], cells[2]
        elif len(cells) == 2:
            cat, area, content = cells[0], "", cells[1]
        else:
            continue
        out.append(f"| {cat} | {area} | {content} |")
    return "\n".join(out)


def collect_tables(doc, start, end):
    """범위 내 표 탐지 → 연속 페이지 표는 하나의 논리 표로 병합.
    반환: (inject_items, page_rects)
      inject_items: [(page, y0, markdown)]  표를 끼워넣을 위치
      page_rects:   {page: [Rect, ...]}     본문 제외용 bbox
    """
    raw = []
    for pi in range(start, end + 1):
        page = doc.load_page(pi)
        for t in page.find_tables().tables:
            raw.append((pi, fitz.Rect(t.bbox), t.extract()))   # 즉시 추출(페이지 유효할 때)
    raw.sort(key=lambda x: (x[0], x[1].y0))

    groups = []
    for pi, bbox, rows in raw:
        if groups and pi == groups[-1]["last"] + 1:
            g = groups[-1]
            g["rows"] += rows
            g["last"] = pi
            g["rects"].append((pi, bbox))
        else:
            groups.append({"first": (pi, bbox.y0), "rows": list(rows),
                           "last": pi, "rects": [(pi, bbox)]})
    inject = [(g["first"][0], g["first"][1], render_content_table(g["rows"])) for g in groups]
    page_rects = {}
    for g in groups:
        for pi, bbox in g["rects"]:
            page_rects.setdefault(pi, []).append(bbox)
    return inject, page_rects


# ---------- 본문 ----------
def body_lines(doc, start, end, page_rects):
    items = []
    for pi in range(start, end + 1):
        rects = page_rects.get(pi, [])
        for block in doc.load_page(pi).get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                lb = line["bbox"]
                cx, cy = (lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2
                if any(r.contains(fitz.Point(cx, cy)) for r in rects):
                    continue
                txt = "".join(s["text"] for s in line["spans"])
                st = txt.strip()
                if not st:
                    continue
                if st in HEADER_FIRST:
                    continue
                if st.isdigit() and len(st) <= 4:         # 페이지번호(상/하단)
                    continue
                items.append((pi, lb[1], "LINE", txt))
    return items


def convert(start, end, title):
    subnames = {s.strip() for s in title.split(",")} if "," in title else set()
    doc = fitz.open(PDF)
    inject, page_rects = collect_tables(doc, start, end)
    items = body_lines(doc, start, end, page_rects)
    items += [(pi, y, "TABLE", md) for (pi, y, md) in inject]
    items.sort(key=lambda x: (x[0], x[1]))

    md = [f"# {title}", ""]
    buf = []
    mode = None

    def add_heading(text, level):
        nonlocal mode
        flush()
        if md and md[-1] != "":
            md.append("")
        md.append("#" * level + " " + text)
        md.append("")

    def flush():
        nonlocal mode
        if buf:
            text = join_para(buf)
            if mode == "ITEM":
                md.append("- " + text)
            else:
                md.extend([text, ""])
            buf.clear()
        mode = None

    def next_is_code(idx):
        for k in range(idx + 1, min(idx + 4, len(items))):
            if items[k][2] != "LINE":
                break
            kk = classify(items[k][3])
            if kk == "BLANK":
                continue
            return kk == "CODE"
        return False

    for i, (_, _, typ, payload) in enumerate(items):
        if typ == "TABLE":
            flush()
            md.extend(["", payload, ""])
            continue
        raw = payload
        k = classify(raw)
        if k == "CONT":
            if mode is None:
                mode = "PARA"
            buf.append(raw)
            continue
        flush()
        s = raw.strip()
        if k == "ANGLE":
            inner = ANGLE_RE.match(s).group(1)
            if "탐구 활동" in inner:
                add_heading(inner, 5)            # <탐구 활동> (영역 #### 하위)
            elif inner in subnames:
                add_heading(s, 2)                # <과목명N> (쌍 과목 구분, 과학과만 사용)
            else:
                md.extend([inner, ""])           # <없음> 등 = 본문 내용(해설 없음)
        elif k == "NUMSEC":
            add_heading(s, 2)
        elif k == "KORSUB":
            add_heading(s, 3)
        elif k == "PAREN":
            if next_is_code(i):
                add_heading(s, 4)
            else:
                mode = "ITEM"
                buf.append(raw)
        elif k == "SUBHEAD":
            if md and md[-1] != "":
                md.append("")
            md.extend([f"**{s}**", ""])
        elif k == "CODE":
            mode = "ITEM"
            m = re.match(r"^(\[[^\]]+\])\s*", raw)
            buf.append(f"**{m.group(1)}** {raw[m.end():]}")
        elif k == "BULLET":
            mode = "ITEM"
            buf.append(BULLET_RE.sub("", raw))

    flush()
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(md)).strip() + "\n"
    tl = re.escape(title)
    text = re.sub(rf"(# {tl}\n\n){tl}\n\n", r"\1", text, count=1)
    return text


# 성격 본문에서 과목명 추출(교양과: 별도 제목 줄 없음). 꺾쇠/따옴표/밑줄/낫표 순.
TITLE_MARKERS = [re.compile(p) for p in (
    r"<([^>]{2,25})>",
    r"[‘']([^’']{2,25})[’']",
    r"_([^_]{2,25})_",
    r"｢([^｣]{2,25})｣",
)]
APPENDIX_RE = re.compile(r"^\[(별표|부록|부 록)")


def _title_from_text(lines, j):
    blob = " ".join(lines[j:j + 8])
    for rx in TITLE_MARKERS:
        m = rx.search(blob)
        if m:
            return m.group(1).strip()
    # 무표시(예: 보건): 성격 첫 어절에서 조사 제거
    body = lines[j + 2] if j + 2 < len(lines) else ""
    m = re.match(r"^([가-힣]{2,10}?)(?:과는|와는|는|은|이란|이라|란)\b", body)
    return m.group(1) if m else ""


def _safe_name(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip()


def _filename(title):
    """'공통국어1, 공통국어2' → '공통국어', 단일 과목은 그대로."""
    if "," in title:
        base = re.sub(r"\d+$", "", title.split(",")[0].strip()).strip()
        return _safe_name(base or title)
    return _safe_name(title)


def _area_of(doc, pi):
    """러닝헤더(각 페이지 첫 줄)에서 교과명(…과/…활동) 추출."""
    for p in (pi + 1, pi - 1, pi):
        if 0 <= p < doc.page_count:
            ls = [l for l in doc.load_page(p).get_text().split("\n") if l.strip()]
            h = ls[0].strip() if ls else ""
            if h and h != "고등학교 교육과정" and h.endswith(("과", "활동")):
                return _safe_name(h)
    return "기타"


def discover(doc):
    """문서 전체에서 과목 챕터(상단 '1. 성격 및 목표') 자동 발견.
    반환: [(start, end, title, area)]"""
    found = []
    for i in range(doc.page_count):
        ls = [l for l in doc.load_page(i).get_text().split("\n") if l.strip()]
        for j, l in enumerate(ls[:6]):
            if l.strip() == "1. 성격 및 목표":
                title = ls[j - 1].strip() if j >= 1 else ""
                if title.isdigit() or not title:        # 교양과: 제목 줄 없음 → 성격 본문에서
                    title = _title_from_text(ls, j) or title
                found.append((i, title, _area_of(doc, i)))
                break
    out = []
    for k, (p, t, a) in enumerate(found):
        raw_end = found[k + 1][0] - 1 if k + 1 < len(found) else doc.page_count - 1
        out.append((p, raw_end, t, a))
    return out


def effective_end(doc, start, end):
    """3.교수학습평가 뒤에 붙는 [별표]/[부록] 부록 페이지는 본문에서 제외."""
    for pi in range(start + 1, end + 1):
        ls = [l for l in doc.load_page(pi).get_text().split("\n") if l.strip()]
        if ls and APPENDIX_RE.match(ls[0].strip()):
            return pi - 1
    return end


if __name__ == "__main__":
    import os
    outroot = sys.argv[1] if len(sys.argv) > 1 else "2022 개정 고등학교 교육과정"
    area_filter = sys.argv[2] if len(sys.argv) > 2 else None   # 교과명 일부 필터(검증용)

    doc0 = fitz.open(PDF)
    subjects = discover(doc0)
    print(f"발견 과목: {len(subjects)}")
    for start, raw_end, title, area in subjects:
        if area == "창의적 체험활동":      # 비표준(활동 영역) — 별도 처리 필요, 스킵
            continue
        if area_filter and area_filter not in area:
            continue
        end = effective_end(doc0, start, raw_end)
        fname = _filename(title)
        outdir = os.path.join(outroot, area)
        os.makedirs(outdir, exist_ok=True)
        out = convert(start, end, title)
        path = os.path.join(outdir, fname + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"  [{area}] {fname}.md  p{start}-{end}  ({out.count(chr(10))} lines)")
