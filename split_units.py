"""
교과서 합본 MD를 8개 대단원 MD로 분할.

두 가지 분할 모드 지원:
- "line": 단원이 시작되는 줄 번호 (예: "이 단원에서는" 패턴이 잡히는 출판사)
- "page": PyMuPDF 페이지 마커(`<!-- PAGE N -->`)를 이용한 페이지 번호 (TOC가 있는 출판사용)
"""
import os, re

BASE = r"C:\Users\choij\agent\textbook"

GRADE3_TITLES = [
    "화학 반응의 규칙과 에너지 변화",
    "기권과 날씨",
    "운동과 에너지",
    "자극과 반응",
    "생식과 유전",
    "에너지 전환과 보존",
    "별과 우주",
    "과학기술과 인류 문명",
]

GRADE2_TITLES = [
    "물질의 특성",
    "지권의 변화",
    "빛과 파동",
    "물질의 구성",
    "식물과 에너지",
    "동물과 에너지",
    "전기와 자기",
    "별과 우주",
]

HS_PHYSICS_TITLES = ["힘과 에너지", "전기와 자기", "빛과 물질"]
HS_CHEM_TITLES    = ["화학의 언어", "물질의 구조와 성질", "화학 평형", "역동적인 화학 반응"]
HS_BIO_TITLES     = ["생명 시스템의 구성", "항상성과 몸의 조절", "생명의 연속성과 다양성"]
HS_EARTH_TITLES   = ["대기와 해양의 상호작용", "지구의 역사와 한반도의 암석", "태양계 천체와 별과 우주의 진화"]

# (학년 폴더, 출판사, MD 파일명, 모드, boundary, 단원 제목 리스트)
JOBS = [
    # 중3 (모두 line 모드)
    ("2015 개정 중학교 3학년", "동아",   "2015 개정 중학교 3학년 과학_동아.md",   "line", [2, 719, 1550, 2247, 2990, 3847, 4490, 5035], GRADE3_TITLES),
    ("2015 개정 중학교 3학년", "미래엔", "2015 개정 중학교 3학년 과학_미래엔.md", "line", [17, 950, 1870, 2886, 3687, 4624, 5305, 5914], GRADE3_TITLES),
    ("2015 개정 중학교 3학년", "비상",   "2015 개정 중학교 3학년 과학_비상.md",   "line", [3, 911, 1892, 2592, 3460, 4345, 4947, 5742], GRADE3_TITLES),
    ("2015 개정 중학교 3학년", "천재",   "2015 개정 중학교 3학년 과학_천재.md",   "line", [7, 878, 1866, 2594, 3256, 4303, 4766, 5346], GRADE3_TITLES),

    # 중2 - line 모드 ("이 단원에서는" 패턴)
    ("2022 개정 중학교 2학년", "동아",     "동아/(동아출판) 22개정_중학_과학2_교과서.md",   "line", [174, 1516, 2263, 3048, 3879, 4450, 5180, 6052], GRADE2_TITLES),
    ("2022 개정 중학교 2학년", "YBM",      "YBM/과학 2(권우진)_공통자료_교과서 PDF.md",     "line", [9, 1568, 2367, 3275, 4122, 4677, 5529, 6171], GRADE2_TITLES),
    ("2022 개정 중학교 2학년", "천재(임)", "천재(임)/중_과학2(임성숙)_교과서.md",            "line", [279, 1103, 1834, 2584, 3283, 3701, 4458, 5417], GRADE2_TITLES),
    ("2022 개정 중학교 2학년", "천재(정)", "천재(정)/중_과학2(정대홍)_교과서.md",            "line", [239, 1855, 3167, 4451, 5594, 6429, 7599, 8855], GRADE2_TITLES),

    # 중2 - page 모드 (페이지 마커)
    ("2022 개정 중학교 2학년", "지학사", "지학사/중등과학_2_교과서(지학사).md",       "page", [13, 47, 95, 135, 167, 193, 229, 267], GRADE2_TITLES),
    ("2022 개정 중학교 2학년", "비상",   "비상/[비상교육] 중학_과학 2_교과서.md",     "page", [8, 42, 88, 128, 162, 188, 226, 266], GRADE2_TITLES),
    ("2022 개정 중학교 2학년", "미래엔", "미래엔/미래엔_과학2_교과서_합본.md",        "page", [1, 41, 83, 123, 157, 187, 229, 267], GRADE2_TITLES),

    # 고등 물리학 (힘과 에너지 / 전기와 자기 / 빛과 물질)
    ("2022 개정 고등학교 물리학", "동아",     "[동아출판] 물리학.md",        "line", [1, 2145, 4141], HS_PHYSICS_TITLES),
    ("2022 개정 고등학교 물리학", "미래엔",   "[미래엔] 물리학.md",          "line", [1, 3067, 5210], HS_PHYSICS_TITLES),
    ("2022 개정 고등학교 물리학", "비상",     "[비상교육] 물리학(손정우).md", "line", [1, 2655, 4500], HS_PHYSICS_TITLES),
    ("2022 개정 고등학교 물리학", "천재",     "[천재] 물리학(최혁준).md",    "line", [1, 4779, 7461], HS_PHYSICS_TITLES),

    # 고등 화학 (화학의 언어 / 물질의 구조와 성질 / 화학 평형 / 역동적인 화학 반응)
    ("2022 개정 고등학교 화학", "동아",   "[동아출판] 화학.md",      "line", [1, 2433, 3906, 5789], HS_CHEM_TITLES),
    ("2022 개정 고등학교 화학", "미래엔", "[미래엔] 화학.md",        "line", [1, 1519, 3097, 4664], HS_CHEM_TITLES),
    ("2022 개정 고등학교 화학", "비상",   "[비상교육] 화학(최원호).md","line", [1, 1996, 3107, 4426], HS_CHEM_TITLES),
    ("2022 개정 고등학교 화학", "천재",   "[천재] 화학(임희준).md",   "line", [1, 2052, 3515, 5112], HS_CHEM_TITLES),

    # 고등 생명과학 (생명 시스템의 구성 / 항상성과 몸의 조절 / 생명의 연속성과 다양성)
    ("2022 개정 고등학교 생명과학", "동아",   "[동아출판] 생명과학.md",        "line", [1, 1859, 3966], HS_BIO_TITLES),
    ("2022 개정 고등학교 생명과학", "미래엔", "[미래엔] 생명과학.md",          "line", [1, 2648, 5058], HS_BIO_TITLES),
    ("2022 개정 고등학교 생명과학", "비상",   "[비상교육] 생명과학(심규철).md", "line", [1, 2888, 5021], HS_BIO_TITLES),
    ("2022 개정 고등학교 생명과학", "천재",   "[천재] 생명과학(이준규).md",    "line", [1, 2956, 5236], HS_BIO_TITLES),

    # 고등 지구과학 (대기와 해양의 상호작용 / 지구의 역사와 한반도의 암석 / 태양계 천체와 별과 우주의 진화)
    ("2022 개정 고등학교 지구과학", "동아",   "[동아출판] 지구과학.md",        "line", [1, 2370, 4416], HS_EARTH_TITLES),
    ("2022 개정 고등학교 지구과학", "미래엔", "[미래엔] 지구과학.md",          "line", [1, 2599, 4655], HS_EARTH_TITLES),
    ("2022 개정 고등학교 지구과학", "비상",   "[비상교육] 지구과학(이기영).md", "line", [1, 3726, 6012], HS_EARTH_TITLES),
    ("2022 개정 고등학교 지구과학", "천재",   "[천재] 지구과학(오필석).md",    "line", [1, 3254, 5181], HS_EARTH_TITLES),
]


def safe(name):
    return name.replace(" ", "").replace("/", "_")


def split_by_lines(md_path, line_starts, titles, out_dir):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    boundaries = line_starts + [len(lines) + 1]
    for i, title in enumerate(titles):
        s = boundaries[i] - 1
        e = boundaries[i + 1] - 1
        chunk = "".join(lines[s:e])
        # 페이지 마커가 있을 경우 제거
        chunk = re.sub(r"<!-- PAGE \d+ -->\n?", "", chunk)
        fname = f"{i+1:02d}_{safe(title)}.md"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(chunk)
        print(f"    {fname}: {len(chunk):>7}B / {chunk.count(chr(10)):>5} lines")


def split_by_pages(md_path, page_starts, titles, out_dir):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    parts = re.split(r"<!-- PAGE (\d+) -->\n?", content)
    page_to_text = {}
    for i in range(1, len(parts), 2):
        page_to_text[int(parts[i])] = parts[i + 1]
    max_page = max(page_to_text.keys()) if page_to_text else 0
    boundaries = page_starts + [max_page + 1]
    for i, title in enumerate(titles):
        s_page = boundaries[i]
        e_page = boundaries[i + 1]
        chunk_parts = [page_to_text.get(p, "") for p in range(s_page, e_page)]
        chunk = "".join(chunk_parts)
        fname = f"{i+1:02d}_{safe(title)}.md"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(chunk)
        print(f"    {fname}: {len(chunk):>7}B / {chunk.count(chr(10)):>5} lines  (p.{s_page}-{e_page-1})")


for grade_dir, pub, md_rel, mode, boundary, titles in JOBS:
    md_path = os.path.join(BASE, grade_dir, md_rel)
    out_dir = os.path.join(BASE, grade_dir, "split", pub)
    if not os.path.exists(md_path):
        print(f"SKIP (없음): {md_path}")
        continue
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n=== {grade_dir} / {pub} ({mode}) ===")
    if mode == "line":
        split_by_lines(md_path, boundary, titles, out_dir)
    else:
        split_by_pages(md_path, boundary, titles, out_dir)
