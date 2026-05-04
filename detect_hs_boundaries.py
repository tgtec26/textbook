"""고등학교 교과서 MD에서 대단원 경계 줄번호 자동 탐지.

교과서 PDF에서 추출된 MD는 매 페이지마다 단원 헤더가 반복된다.
TOC 영역과 실제 단원 본문을 구분하기 위해:
  - 단원 헤더 발견 후 이후 200줄 안에 같은 단원 헤더가 3번 이상 더 나타나는
    첫 번째 위치를 실제 단원 시작으로 판단.
"""
import os, re

BASE = r"C:\Users\choij\agent\textbook"

SUBJECTS = {
    "물리학": {
        "folder_key": "고등학교 물리학",
        "units": ["힘과 에너지", "전기와 자기", "빛과 물질"],
    },
    "화학": {
        "folder_key": "고등학교 화학",
        "units": ["화학의 언어", "물질의 구조와 성질", "화학 평형", "역동적인 화학 반응"],
    },
    "생명과학": {
        "folder_key": "고등학교 생명과학",
        "units": ["생명 시스템의 구성", "항상성과 몸의 조절", "생명의 연속성과 다양성"],
    },
    "지구과학": {
        "folder_key": "고등학교 지구과학",
        "units": ["대기와 해양의 상호작용", "지구의 역사와 한반도의 암석",
                  "태양계 천체와 별과 우주의 진화"],
    },
}

ROMAN_PAT = re.compile(r"^[ⅠⅡⅢⅣⅤ]\s*\.\s*|^(?:I{1,3}V?|IV)\s*\.\s*")

def find_unit_start(lines, keyword, min_line=1, window=200, min_repeat=3):
    """
    keyword를 포함하는 줄 중,
    이후 window 줄 안에 같은 keyword가 min_repeat번 이상 더 나오는
    첫 번째 줄을 반환 (1-indexed).
    min_line 이후부터만 탐색.
    """
    n = len(lines)
    candidates = [
        i for i, line in enumerate(lines)
        if i >= min_line - 1
        and keyword in line.strip()
        and ROMAN_PAT.match(line.strip())
        and '쪽' not in line.strip()
    ]
    for idx in candidates:
        # 이후 window 줄 안에 몇 번 더 나오나
        count = sum(
            1 for j in range(idx + 1, min(idx + 1 + window, n))
            if keyword in lines[j] and ROMAN_PAT.match(lines[j].strip())
        )
        if count >= min_repeat:
            return idx + 1  # 1-indexed
    # 완화: min_repeat=1 로 재탐색
    for idx in candidates:
        count = sum(
            1 for j in range(idx + 1, min(idx + 1 + window, n))
            if keyword in lines[j] and ROMAN_PAT.match(lines[j].strip())
        )
        if count >= 1:
            return idx + 1
    return candidates[0] + 1 if candidates else None

for subj, info in SUBJECTS.items():
    folder = None
    for d in os.listdir(BASE):
        if info["folder_key"] in d:
            folder = os.path.join(BASE, d)
            break
    if not folder:
        print(f"폴더 없음: {subj}")
        continue

    units = info["units"]
    print(f"\n{'='*65}")
    print(f"[{subj}]  단원: {units}")
    print(f"{'='*65}")

    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".md") or fname.endswith(".raw.md"):
            continue
        md_path = os.path.join(folder, fname)
        with open(md_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        bounds = [1]
        prev = 1
        for uname in units[1:]:
            ln = find_unit_start(lines, uname, min_line=prev + 100)
            bounds.append(ln)
            if ln:
                prev = ln

        print(f"\n  {fname}  ({len(lines)} lines)")
        for uname, ln in zip(units, bounds):
            print(f"    {uname:45s} → L{ln}")
        print(f"    → boundaries = {bounds}")
