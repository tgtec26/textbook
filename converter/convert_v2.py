#!/usr/bin/env python3
"""교과서 PDF(한 쪽씩 보이는 PDF) → Markdown 변환기 v2.

기존 변환기(run_drive_conversion.py)의 문제를 줄이기 위해 글자 위치만 보지 않고
글꼴·크기·색·그림 영역을 함께 쓴다.

- 본문 / 보조단 구분: 본문 글꼴로 쓴 긴 줄의 좌우 끝으로 본문 단 폭을 구하고, 그 바깥 줄은 보조단
- 문단 중간 줄바꿈: PDF가 줄 끝에 공백을 남긴 경우에만 띄어쓰고, 아니면 붙여서 한 문단으로 이음
- 그림 속 글자: 그림(이미지·벡터 지도) 영역 안의 짧은 글자는 본문에서 빼서 "그림 속 글자"로 따로 모음
- 그림자·테두리로 두 번 그려진 글자, 줄 번호(5·10·15), 장식용 한 글자는 제거하고 보고서에 기록
"""
import argparse
import json
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

import fitz

CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f​‌‍﻿]")
LIST_START_RE = re.compile(r"^(\d+[.)]\s|[①-⑳]|[가-하][.)]|\([가-하0-9]+\)|[•·▪■□○●]\s|\[|자료\s*\d)")
CAPTION_RE = re.compile(r"^자료\s*\d")
LATIN_RE = re.compile(r"[A-Za-z0-9]")
TAG_COLORS = {0x1FBBD7}
TICK_RE = re.compile(r"^[\-−+]?[\d\s.,]+(?:%|℃|°|㎜|mm|\(월\)|\(년\))?$")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\u2000-\u200a\u00a0\u3000]", " ", text)
    return CONTROL_RE.sub("", text).replace("\t", " ")


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


class Line:
    __slots__ = ("runs", "text", "x0", "y0", "x1", "y1", "size", "font", "color", "rot", "role", "drop", "label")

    def __init__(self, raw: dict):
        spans = [s for s in raw["spans"] if norm(s["text"]).strip() != "" or s["text"].strip(" ") == ""]
        self.runs = [(norm(s["text"]), s["font"], round(s["size"], 1), s["color"]) for s in spans]
        self.text = "".join(r[0] for r in self.runs)
        self.x0, self.y0, self.x1, self.y1 = raw["bbox"]
        self.restyle()
        self.rot = abs(raw["dir"][1]) > 0.03
        self.role = "body"
        self.drop = None
        self.label = False

    def restyle(self):
        """글자 수가 가장 많은 글꼴·크기·색을 줄의 대표 스타일로 삼는다."""
        weight = Counter()
        for t, f, sz, c in self.runs:
            weight[(f, sz, c)] += len(t.strip())
        (self.font, self.size, self.color), _ = (weight.most_common(1) or [(("", 0, 0), 0)])[0]

    @property
    def ink_x1(self):
        """줄 끝 공백 글자가 차지한 폭을 뺀 오른쪽 끝."""
        trailing = len(self.text) - len(self.text.rstrip(" "))
        return self.x1 - (self.x1 - self.x0) * trailing / max(1, len(self.text))

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2

    @property
    def clen(self):
        return len(compact(self.text))


def collect_lines(page) -> list[Line]:
    out = []
    for block in page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]:
        if block["type"] != 0:
            continue
        for raw in block["lines"]:
            line = Line(raw)
            if line.text.strip():
                out.append(line)
    return out


def figure_regions(page, lines: list[Line], body) -> list[tuple]:
    """그림·지도 후보 영역. 안에 든 글자가 짧은 조각 위주일 때만 '그림 속 글자'로 취급한다."""
    cands = []
    for img in page.get_image_info():
        r = fitz.Rect(img["bbox"])
        if r.get_area() >= 15000:
            cands.append(r)
    for r in page.cluster_drawings():
        if r.get_area() >= 6000:
            cands.append(fitz.Rect(r))
    regions = []
    for r in cands:
        inside = [l for l in lines if r.contains(fitz.Point(l.cx, l.cy)) and not l.label]
        if len(inside) < 4:
            continue
        if statistics.median(l.clen for l in inside) > 14:  # 긴 문장이 든 영역은 설명 상자이지 그림이 아니다
            continue
        # 지도 글자는 한 글꼴로 많이 찍힌다. 그 글꼴(또는 아주 짧은 조각)만 그림 속 글자로 보고,
        # 같은 영역 안의 다른 글꼴 설명문은 본문으로 남긴다.
        by_font = {}
        for l in inside:
            by_font.setdefault(l.font, []).append(l.clen)
        label_fonts = {f for f, v in by_font.items() if len(v) >= 3 and statistics.median(v) <= 8}
        prose = {f for f, v in by_font.items() if statistics.median(v) >= 14}
        labels = [l for l in inside if (l.font, l.size) != body and (l.font in label_fonts or l.clen <= 6 or (l.clen <= 12 and l.font not in prose))]
        if not labels:
            continue
        regions.append((r, labels))
    return regions


def body_style(lines: list[Line]):
    """본문 글꼴·크기: 폭 150pt 이상인 줄의 글자 수 합이 가장 큰 스타일."""
    weight = Counter()
    for l in lines:
        if l.rot or l.x1 - l.x0 < 150:
            continue
        weight[(l.font, l.size)] += l.clen
    return weight.most_common(1)[0][0] if weight else None


def mark_duplicates(lines: list[Line]):
    """그림자·테두리로 같은 자리에 두 번 찍힌 글자는 하나만 남긴다."""
    seen = {}
    for l in sorted(lines, key=lambda l: (round(l.y0 / 3), l.x0)):
        key = (compact(l.text), round(l.y0 / 4), round(l.x0 / 4))
        if key in seen:
            l.drop = "중복(그림자·테두리)"
            continue
        seen[key] = l
    # 같은 글이 일부만 한 번 더 겹쳐 찍힌 줄(굵은 머리말 조각 등)은 작은 쪽을 버린다
    live = [l for l in lines if not l.drop and l.clen >= 3]
    for small in live:
        for big in live:
            if small is big or small.drop or big.clen <= small.clen:
                continue
            ix = min(small.x1, big.x1) - max(small.x0, big.x0)
            iy = min(small.y1, big.y1) - max(small.y0, big.y0)
            if ix > 0.8 * (small.x1 - small.x0) and iy > 0.6 * (small.y1 - small.y0) and compact(small.text) in compact(big.text):
                small.drop = "중복(그림자·테두리)"
                break


def mark_noise(lines: list[Line], page_h: float, body_size: float, report: dict):
    """장식·줄 번호·인쇄 표지·역량 꼬리표 제거 표시 후 보고서에 기록."""
    for l in lines:
        if l.drop:
            continue
        c = compact(l.text)
        if re.fullmatch(r"\d{1,2}", c) and l.size <= body_size - 2 and l.color != 0x231F20 and l.y0 < page_h * 0.92:
            l.drop = "줄 번호"
        elif ".indd" in l.text or re.search(r"\d{4}\.\s?\d{1,2}\.\s?\d{1,2}", l.text):
            l.drop = "인쇄 파일 표지"
        elif l.size >= 40:
            l.drop = "장식 큰 글자"
        elif l.rot and l.clen <= 1 and l.size < 12:
            l.drop = "장식 한 글자"
        elif l.clen <= 1 and l.size < body_size - 1.5 and not c.isdigit():
            l.drop = "장식 한 글자"
        elif l.size < 7.5 and l.color in TAG_COLORS and l.clen <= 8:
            l.drop = "역량 꼬리표(정보 활용 등)"
    for l in lines:
        if l.drop:
            report["dropped"][l.drop] = report["dropped"].get(l.drop, 0) + 1
            report["dropped_samples"].setdefault(l.drop, [])
            if len(report["dropped_samples"][l.drop]) < 5:
                report["dropped_samples"][l.drop].append(l.text.strip()[:30])


def dedupe_headings(lines: list[Line]):
    """같은 제목이 흰 그림자 + 검은 글자로 두 번 나온 경우 번호가 붙은 쪽만 남긴다."""
    live = [l for l in lines if not l.drop]
    for a in live:
        for b in live:
            if a is b or a.drop or b.drop or abs(a.y0 - b.y0) > 14:
                continue
            ka = re.sub(r"^\d+", "", compact(a.text))
            kb = re.sub(r"^\d+", "", compact(b.text))
            if ka and ka == kb and len(compact(a.text)) > len(compact(b.text)):
                b.drop = "중복(그림자·테두리)"


def page_label(lines: list[Line], page_h: float):
    """쪽 하단에서 쪽 번호를 찾는다. 찾으면 해당 줄에 drop 표시."""
    found = None
    for l in sorted([l for l in lines if l.y0 > page_h * 0.92 and not l.drop], key=lambda l: l.y0):
        m = re.search(r"(?:^|\s)(\d{1,3})\s*$", l.text) or re.match(r"^(\d{1,3})\s", l.text)
        if m and found is None:
            found = int(m.group(1))
            l.drop = "쪽 번호"
        elif l.clen <= 14 and re.search(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|^\.\s|^\d+\.\s", l.text):
            l.drop = "쪽 번호"  # 쪽 번호 옆 단원 표지
    return found


def split_zones(lines: list[Line], body, page_w: float):
    """본문 단 [mx0, mx1]을 구하고 단 바깥 줄은 side로 표시."""
    longs = [l for l in lines if (l.font, l.size) == body and l.x1 - l.x0 >= 150] if body else []
    if not longs:
        return None
    mx0 = statistics.median(sorted(l.x0 for l in longs)[:max(3, len(longs) // 3)])
    mx1 = statistics.median(sorted(l.x1 for l in longs)[-max(3, len(longs) // 3):])
    for l in lines:
        if l.role == "figure":
            continue
        if l.x0 > mx1 + 8 or l.x1 < mx0 - 8:
            l.role = "side"
    return mx0, mx1


def build_runs(line: Line, body) -> str:
    """본문 줄 안에서 본문과 다른 글꼴·색으로 쓴 낱말(굵은 용어, 소제목 머리말)을 **강조**로 표시.
    쓰기 전에 번호 머리표(1, 2…)와 구두점만 다른 글꼴인 경우는 강조하지 않는다."""
    if not body or (line.font, line.size) != body:
        return line.text
    runs = []
    for run in line.runs:
        if runs and runs[-1][1:] == run[1:]:
            runs[-1] = (runs[-1][0] + run[0],) + run[1:]
        else:
            runs.append(run)
    parts = []
    for i, (t, f, sz, c) in enumerate(runs):
        core = t.strip()
        differs = (f, sz) != body or c != line.color
        if i == 0 and re.fullmatch(r"\d{1,2}", core) and len(runs) > 1:
            parts.append(core + ". ")  # 번호 머리표
        elif differs and sz >= body[1] - 2 and re.search(r"[가-힣A-Za-z]", core):
            parts.append("**" + core + "**" + (" " if t.endswith(" ") else ""))
        else:
            parts.append(t)
    return "".join(parts)


def x_gap(a: Line, b: Line) -> float:
    return max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1))


def glyph_rows(group: list[Line]) -> list[list[Line]]:
    """낱글자 줄을 행으로 묶는다. 대부분 비스듬한 글자(곡선 제목)는 왼쪽에서 오른쪽으로 훑으며
    가장 가까운 행에 붙이고, 그렇지 않으면 세로 위치로 행을 나눈다."""
    rows: list[list[Line]] = []
    if group[0].size >= 18 and sum(g.rot for g in group) >= 0.6 * len(group):
        for g in sorted(group, key=lambda g: g.cx):
            fits = [r for r in rows if g.cx > r[-1].cx and abs(g.cy - r[-1].cy) < 20]
            if fits:
                min(fits, key=lambda r: abs(g.cy - r[-1].cy)).append(g)
            else:
                rows.append([g])
    else:
        for g in sorted(group, key=lambda g: g.cy):
            if rows and abs(g.cy - rows[-1][0].cy) < 0.63 * g.size:
                rows[-1].append(g)
            else:
                rows.append([g])
        rows = [sorted(r, key=lambda x: x.x0) for r in rows]
    rows.sort(key=lambda r: statistics.mean(x.cy for x in r))
    return rows


def merge_glyph_labels(lines: list[Line], body_size: float) -> list[Line]:
    """'해보자', '스스로 점검'처럼 글자를 하나씩 따로 그린 라벨을 한 줄로 복원한다.
    같은 글꼴·크기·색의 한두 글자 줄이 30pt 안에 모여 있으면 한 라벨로 본다."""
    small = [l for l in lines if l.clen <= 2 and not l.drop and l.size >= 9]
    used, labels = set(), []
    for l in small:
        if id(l) in used:
            continue
        group = [l]
        used.add(id(l))
        grew = True
        while grew:
            grew = False
            for m in small:
                if id(m) in used or (m.font, m.color) != (l.font, l.color) or abs(m.size - l.size) > 6:
                    continue
                if any(x_gap(m, g) < 10 and abs(m.cy - g.cy) < 22 for g in group):
                    group.append(m)
                    used.add(id(m))
                    grew = True
        if len(group) < 3:
            for g in group:
                used.discard(id(g))
            continue
        rows = glyph_rows(group)
        text = " ".join("".join(x.text for x in r).strip() for r in rows)
        text = re.sub(r"\s+", " ", text)
        first = group[0]
        first.label = True
        first.rot = False
        first.runs = [(text, first.font, first.size, first.color)]
        first.text = text
        first.x0, first.y0 = min(g.x0 for g in group), min(g.y0 for g in group)
        first.x1, first.y1 = max(g.x1 for g in group), max(g.y1 for g in group)
        first.restyle()
        for g in group[1:]:
            g.drop = "라벨 낱글자(병합됨)"
        labels.append(first)
    return lines


def row_merge(lines: list[Line]) -> list[Line]:
    """같은 단 안에서 같은 높이에 나란한 조각(번호 + 문장, '자료 1' + 설명)을 한 줄로 합친다.
    조각이 짧거나(4자 이하) 바로 이어진 경우만 합쳐서, 본문과 옆 보조단이 한 줄이 되지 않게 한다."""
    merged = sorted(lines, key=lambda l: (l.y0 - (10 if l.label else 0), l.x0))
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(merged):
            for b in merged[i + 1:]:
                if a.label or b.label:
                    continue
                left, right = (a, b) if a.x0 <= b.x0 else (b, a)
                overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
                gap_x = right.x0 - left.x1
                fragment = min(a.clen, b.clen) <= 4 and 0 <= gap_x < 28
                if overlap > 0.5 * min(a.y1 - a.y0, b.y1 - b.y0) and (fragment or 0 <= gap_x < 14):
                    gap = " " if not left.text.endswith(" ") else ""
                    left.runs += [(gap, right.font, right.size, right.color)] + right.runs
                    left.text += gap + right.text
                    left.x1, left.y0 = max(left.x1, right.x1), min(left.y0, right.y0)
                    left.y1 = max(left.y1, right.y1)
                    left.restyle()
                    merged.remove(right)
                    changed = True
                    break
            if changed:
                break
    return sorted(merged, key=lambda l: (l.y0 - (10 if l.label else 0), l.x0))


def overlap_frac(a: Line, b: Line) -> float:
    ix = min(a.x1, b.x1) - max(a.x0, b.x0)
    return max(0.0, ix) / max(1.0, min(a.x1 - a.x0, b.x1 - b.x0))


def xy_groups(lines: list[Line], min_vgap: float = 14.0) -> list[list[Line]]:
    """XY-cut. 글이 하나도 가로지르지 않는 세로 빈 띠가 있으면 좌우로, 없으면 가장 큰 가로 빈 띠에서
    위아래로 나눠 읽는 순서의 묶음(단)을 만든다. 나란한 자료 상자 두세 개가 한 줄씩 섞이는 것을 막는다."""
    if len(lines) <= 1:
        return [lines] if lines else []
    best = None  # (gap, left set)
    ordered = sorted(lines, key=lambda l: l.x0)
    reach = ordered[0].x1
    for i, l in enumerate(ordered[1:], 1):
        if l.x0 - reach >= min_vgap and (best is None or l.x0 - reach > best[0]):
            best = (l.x0 - reach, ordered[:i])
        reach = max(reach, l.x1)
    if best:
        left = best[1]
        right = [l for l in lines if l not in left]
        return xy_groups(left, min_vgap) + xy_groups(right, min_vgap)
    heights = sorted(l.y1 - l.y0 for l in lines)
    min_hgap = max(10.0, 0.9 * heights[len(heights) // 2])
    ordered = sorted(lines, key=lambda l: l.y0 - (10 if l.label else 0))
    best = None
    reach = ordered[0].y1
    for i, l in enumerate(ordered[1:], 1):
        gap = l.y0 - (10 if l.label else 0) - reach
        if gap >= min_hgap and (best is None or gap > best[0]):
            best = (gap, ordered[:i])
        reach = max(reach, l.y1)
    if best:
        top = best[1]
        bottom = [l for l in ordered if l not in top]
        return xy_groups(top, min_vgap) + xy_groups(bottom, min_vgap)
    return [ordered]


def assemble(lines: list[Line], body, bounds=None) -> list[str]:
    """줄을 읽는 순서로 묶어 문단으로 만든다."""
    out = []
    lines = row_merge(lines)
    for group in xy_groups(lines):
        if bounds and sum(overlap_frac(l, fake_bounds(bounds)) for l in group) >= 0.5 * len(group):
            out += assemble_group(group, body, bounds)
        else:
            out += assemble_group(group, body, None)
    return out


class fake_bounds:
    """overlap_frac에 넘기기 위한 가로 구간 표지."""
    def __init__(self, bounds):
        self.x0, self.x1 = bounds


def assemble_group(lines: list[Line], body, bounds=None) -> list[str]:
    """한 묶음(단)의 줄을 문단으로 묶는다. bounds는 본문 단의 (왼쪽, 오른쪽) 끝."""
    if not lines:
        return []
    if bounds:
        col_x0, col_x1 = bounds
    else:
        col_x0 = min(l.x0 for l in lines)
        col_x1 = max(l.x1 for l in lines if l.clen > 6) if any(l.clen > 6 for l in lines) else max(l.x1 for l in lines)
    body_size = body[1] if body else statistics.median(l.size for l in lines)
    paras: list[list] = []  # [text, kind]
    prev = None
    for l in lines:
        c = compact(l.text)
        heading = l.label or (l.size >= body_size + 2.5 and l.clen > 1 and not c.isdigit())
        marker = c.isdigit() and l.size >= body_size + 2.5
        text = build_runs(l, body).strip()
        if heading:
            text = "#### " + re.sub(r"\s+", " ", text)
        new = prev is None or heading or marker or prev["kind"] != ("h" if heading else "p")
        if not new:
            # 줄 끝 공백 글자 폭 때문에 본문 줄도 단 오른쪽 끝을 조금 넘을 수 있어 여유를 둔다
            outsider = prev["x1"] > col_x1 + 16 or l.ink_x1 > col_x1 + 16 or abs(l.x0 - prev["x0"]) > 40
            short = prev["x1"] < col_x1 - 14 or outsider
            indent = l.x0 > col_x0 + 5 and prev["x0"] <= col_x0 + 5
            new = short or indent or bool(LIST_START_RE.match(l.text.strip())) or (l.y0 - prev["y1"] > 0.9 * (l.y1 - l.y0))
        if new:
            paras.append([text, "h" if heading else "p"])
        else:
            # 한글은 줄바꿈이 낱말 중간에서 일어나므로 PDF가 줄 끝 공백을 남긴 경우에만 띄운다
            latin_break = LATIN_RE.search(prev["raw"][-1:]) and LATIN_RE.search(l.text.strip()[:1])
            joiner = " " if (latin_break or prev["raw"].endswith(" ")) else ""
            paras[-1][0] += joiner + text
        prev = {"raw": l.text, "x0": l.x0, "x1": l.ink_x1, "y1": l.y1, "kind": "h" if heading else "p"}
        if marker:
            prev["kind"] = "m"
    out = []
    for text, _ in paras:
        text = re.sub(r"[ ]{2,}", " ", text).strip()
        text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
        if text:
            out.append(text)
    return out


def convert_page(page, report: dict):
    lines = collect_lines(page)
    h, w = page.rect.height, page.rect.width
    body = body_style(lines)
    body_size = body[1] if body else 10.0
    mark_duplicates(lines)
    merge_glyph_labels(lines, body_size)
    mark_noise(lines, h, body_size, report)
    dedupe_headings(lines)
    label = page_label(lines, h)
    live = [l for l in lines if not l.drop]

    # 그림 속 글자
    fig_text = []
    for _, items in figure_regions(page, live, body):
        items = [l for l in items if l.role != "figure"]
        for l in items:
            l.role = "figure"
        items.sort(key=lambda l: (round(l.y0 / 6), l.x0))
        seen, texts = set(), []
        for l in items:
            t = re.sub(r"\s+", " ", l.text).strip()
            if t and t not in seen:
                seen.add(t)
                texts.append(t)
        if texts:
            fig_text.append(" · ".join(texts))
    ticks = [l for l in live if l.role != "figure" and not l.label and l.size <= body_size - 0.5 and TICK_RE.match(l.text.strip())]
    if ticks:
        ticks.sort(key=lambda l: (round(l.y0 / 6), l.x0))
        fig_text.append(" · ".join(re.sub(r"\s+", " ", l.text).strip() for l in ticks))
        for l in ticks:
            l.role = "figure"
    live = [l for l in live if l.role != "figure"]
    live_chars = sum(l.clen for l in live)

    bounds = split_zones(live, body, w)

    main = [l for l in live if l.role == "body"]
    side = [l for l in live if l.role == "side"]
    out = {"label": label, "main": assemble(main, body, bounds), "side": assemble(side, body), "figures": fig_text}
    emitted = sum(len(compact(re.sub(r"\*\*|^#+ ", "", t, flags=re.M))) for t in out["main"] + out["side"])
    out["audit"] = emitted - live_chars  # 번호 머리표(N.)만큼 +, 글자 누락·중복이면 크게 어긋남
    return out



def fragmented(page: dict) -> bool:
    """짧은 조각 문단이 절반 넘는 쪽(도표·그림 글자가 본문으로 새어 든 쪽)은 사람이 눈으로 확인할 후보."""
    paras = [t for t in page["main"] + page["side"] if not t.startswith("#")]
    return len(paras) >= 8 and sum(len(t) < 15 for t in paras) / len(paras) > 0.5


def convert(pdf_path: Path, start_label: int | None = None):
    doc = fitz.open(pdf_path)
    report = {"pdf": pdf_path.name, "pages": len(doc), "dropped": {}, "dropped_samples": {}, "unlabeled_pages": []}
    pages = [convert_page(doc[i], report) for i in range(len(doc))]
    report["review_pages"] = [i + 1 for i, p in enumerate(pages) if fragmented(p)]
    report["audit_mismatch"] = {i + 1: p["audit"] for i, p in enumerate(pages) if abs(p["audit"]) > 4}
    # 쪽 번호 보정: 번호가 없는 쪽은 앞 쪽 + 1
    labels = [p["label"] for p in pages]
    for i, lab in enumerate(labels):
        if lab is None:
            if i and labels[i - 1] is not None:
                labels[i] = labels[i - 1] + 1
            elif i + 1 < len(labels) and labels[i + 1] is not None:
                labels[i] = labels[i + 1] - 1
            report["unlabeled_pages"].append(i + 1)
    chunks = [f"# {pdf_path.stem}", ""]
    for p, lab in zip(pages, labels):
        chunks.append(f"## {lab}쪽" if lab is not None else "## ?쪽")
        chunks += p["main"]
        if p["side"]:
            chunks.append("### 보조단")
            chunks += p["side"]
        if p["figures"]:
            chunks.append("### 그림 속 글자")
            chunks += p["figures"]
    return "\n".join(chunks).rstrip() + "\n", report


def main():
    ap = argparse.ArgumentParser(description="교과서 PDF(한 쪽씩) → Markdown v2")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    md, report = convert(args.pdf)
    out = args.output or args.pdf.with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out} ({len(md)}자) 제거: {report['dropped']}")


if __name__ == "__main__":
    main()
