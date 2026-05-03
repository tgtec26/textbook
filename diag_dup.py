"""천재(정) PDF의 중복 의심 페이지 진단."""
import fitz, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
PDF = r"C:\Users\choij\agent\textbook\2022 개정 중학교 2학년\천재(정)\중_과학2(정대홍)_교과서.pdf"
KEY = "디지털 용질의 녹는 양 비교하기"

doc = fitz.open(PDF)
print(f"총 페이지: {len(doc)}")
hits = []
for i in range(len(doc)):
    text = doc.load_page(i).get_text("text")
    text_compact = re.sub(r"\s+", "", text)
    key_compact = re.sub(r"\s+", "", KEY)
    if key_compact in text_compact:
        hits.append((i+1, len(text)))
        print(f"  PDF 페이지 {i+1}: '{KEY}' 발견 ({len(text)} chars)")

# 페이지 18 부근 내용 보기
for p in range(15, 22):
    text = doc.load_page(p-1).get_text("text")[:300]
    print(f"\n=== PDF p.{p} (앞 300자) ===")
    print(text)
doc.close()
