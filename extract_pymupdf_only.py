"""
opendataloader_pdf와 호환되지 않는 PDF를 위한 PyMuPDF 단독 추출.
process_pdf.py와 동일한 cleanup 규칙을 적용해 결과물 형태가 일관되게 한다.
"""
import argparse
import os
import re
import sys
import time

import fitz


def extract(pdf_path):
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.dirname(os.path.abspath(pdf_path))
    raw_md = os.path.join(out_dir, f"{base}.raw.md")
    out_md = os.path.join(out_dir, f"{base}.md")

    print(f"=== {os.path.basename(pdf_path)} (PyMuPDF only) ===", flush=True)
    t0 = time.time()
    doc = fitz.open(pdf_path)
    n = len(doc)
    print(f"  총 페이지: {n}", flush=True)

    with open(raw_md, "w", encoding="utf-8") as f:
        for i in range(n):
            text = doc.load_page(i).get_text("text")
            f.write(text)
            f.write("\n")
    doc.close()
    print(f"  raw -> {raw_md} ({os.path.getsize(raw_md)}B, {time.time()-t0:.1f}s)", flush=True)

    with open(raw_md, "r", encoding="utf-8") as f:
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
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned) + "\n")
    print(f"  cleaned -> {out_md} ({os.path.getsize(out_md)}B / {len(cleaned)} lines)", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="PDF 파일")
    args = parser.parse_args()
    extract(os.path.abspath(args.pdf))


if __name__ == "__main__":
    main()
