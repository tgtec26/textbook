"""모든 *.raw.md 를 다시 cleanup 해서 같은 폴더의 *.md 를 갱신."""
import os, re, glob

BASE = r"C:\Users\choij\agent\textbook"

def cleanup(raw_path, clean_path):
    with open(raw_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r"!\[.*?\]\(.*?\)", "", content, flags=re.DOTALL)
    content = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", content)
    cleaned = []
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        if len(s.split()) > 1:
            cleaned.append(s)
    with open(clean_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned) + "\n")
    return len(cleaned)

count = 0
for root, _, files in os.walk(BASE):
    if ".git" in root or "_chunks" in root or "_recover" in root or ".work" in root:
        continue
    for f in files:
        if f.endswith(".raw.md"):
            raw = os.path.join(root, f)
            clean = raw.replace(".raw.md", ".md")
            n = cleanup(raw, clean)
            print(f"  {n:>6} lines -> {clean}")
            count += 1
print(f"\n{count} 개 파일 재정리 완료")
