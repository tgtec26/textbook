"""각 MD 파일에서 인접한 중복 블록(opendataloader 추출 중복) 자동 검출.

- 각 줄의 정규화 토큰(공백 제거, 짧은 줄 제외)을 만들어
  ±100 줄 이내에 같은 줄이 반복되는 패턴을 찾는다.
- 인접 중복 블록이 5줄 이상 연속이면 강한 의심.
"""
import os, re

BASE = r"C:\Users\choij\agent\textbook"

def normalize(line):
    return re.sub(r"\s+", "", line)

def find_dup_blocks(md_path, window=100, min_block=5):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.readlines()]
    norm = [normalize(l) for l in lines]
    n = len(lines)
    suspicious = []
    i = 0
    while i < n:
        if len(norm[i]) < 20:
            i += 1
            continue
        # 같은 normalized line이 ±window 이내에 다시 등장하는가
        match_j = None
        for j in range(i+5, min(i+window, n)):
            if norm[j] == norm[i]:
                match_j = j
                break
        if match_j is None:
            i += 1
            continue
        # 연속으로 몇 줄까지 일치하는가
        run = 0
        while (i + run < match_j and match_j + run < n
               and norm[i + run] == norm[match_j + run]
               and len(norm[i + run]) >= 10):
            run += 1
        if run >= min_block:
            suspicious.append((i+1, match_j+1, run))
            i = match_j + run
        else:
            i += 1
    return suspicious

found = []
for root, _, files in os.walk(BASE):
    if any(skip in root for skip in (".git", "_chunks", "_recover", ".work", "split", "docs")):
        continue
    for f in files:
        if f.endswith(".md") and not f.endswith(".raw.md"):
            md = os.path.join(root, f)
            blocks = find_dup_blocks(md)
            if blocks:
                found.append((md, blocks))
                print(f"\n=== {md} ===")
                for a, b, r in blocks:
                    print(f"  중복 블록 {r}줄: L{a} ↔ L{b}")

if not found:
    print("중복 의심 블록 없음")
else:
    print(f"\n총 {len(found)}개 파일에 중복 의심 발견")
