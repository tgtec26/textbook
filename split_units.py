"""
Split each publisher's 합본 MD into 8 unit MDs by line boundaries.
"""
import os

BASE = r"C:\Users\choij\agent\textbook"
OUT = os.path.join(BASE, "split")

UNIT_TITLES = [
    "화학 반응의 규칙과 에너지 변화",
    "기권과 날씨",
    "운동과 에너지",
    "자극과 반응",
    "생식과 유전",
    "에너지 전환과 보존",
    "별과 우주",
    "과학기술과 인류 문명",
]

PUBLISHERS = {
    "동아":   {"file": "2025 개정 중학교 3학년 과학_동아.md",
              "starts": [2, 719, 1550, 2248, 2991, 3848, 4491, 5036]},
    "미래엔": {"file": "2025 개정 중학교 3학년 과학_미래엔.md",
              "starts": [17, 950, 1870, 2886, 3687, 4624, 5305, 5914]},
    "비상":   {"file": "2025 개정 중학교 3학년 과학_비상.md",
              "starts": [3, 911, 1892, 2592, 3460, 4345, 4947, 5742]},
    "천재":   {"file": "2025 개정 중학교 3학년 과학_천재.md",
              "starts": [7, 878, 1866, 2594, 3256, 4303, 4766, 5346]},
}

def safe(name):
    """Make a filesystem-safe filename fragment from a Korean unit title."""
    return name.replace(" ", "").replace("/", "_")

for pub, info in PUBLISHERS.items():
    src = os.path.join(BASE, info["file"])
    with open(src, "r", encoding="utf-8") as f:
        lines = f.readlines()
    starts = info["starts"]
    if len(starts) != len(UNIT_TITLES):
        raise SystemExit(f"unit count mismatch for {pub}")

    out_dir = os.path.join(OUT, pub)
    os.makedirs(out_dir, exist_ok=True)

    boundaries = starts + [len(lines) + 1]
    print(f"=== {pub} (총 {len(lines)}줄) ===")
    for i, title in enumerate(UNIT_TITLES):
        s = boundaries[i] - 1   # 1-indexed start → 0-indexed
        e = boundaries[i+1] - 1 # exclusive end (next unit's start)
        chunk = "".join(lines[s:e])
        fname = f"{i+1:02d}_{safe(title)}.md"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(chunk)
        nl = chunk.count("\n")
        print(f"  {fname}: {len(chunk):>7} chars / {nl:>5} lines")
    print()
