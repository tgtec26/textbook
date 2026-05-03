"""
PDF -> Markdown 안전 추출 파이프라인.

특징:
- 각 PDF를 페이지 청크(기본 50p)로 나누어 opendataloader_pdf로 추출.
- 청크 실패 시 10p → 1p 로 재귀 분할하여 손상 페이지를 격리.
- 1p 추출도 실패하면 PyMuPDF로 fallback 텍스트 추출.
- cleanup 전 raw 산출물(`*.raw.md`)을 보존.
- 어떤 페이지가 PyMuPDF fallback으로 처리됐는지 `*.FALLBACK.txt`에 기록.
- 정리 규칙: 이미지 태그 제거, 빈 줄 제거, 단어 1개뿐인 줄 제거.

사용:
    python process_pdf.py <PDF 또는 디렉터리> [--chunk-size 50] [--keep-chunks]
"""
import argparse
import glob
import logging
import os
import re
import shutil
import sys
import time

import opendataloader_pdf

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

log = logging.getLogger("process_pdf")


def get_page_count(pdf_path):
    if fitz is None:
        raise RuntimeError("PyMuPDF가 필요합니다: pip install pymupdf")
    with fitz.open(pdf_path) as doc:
        return len(doc)


def extract_chunk(pdf_path, start, end, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    try:
        opendataloader_pdf.convert(
            pdf_path,
            output_dir=out_dir,
            format="markdown",
            image_output="off",
            quiet=True,
            pages=f"{start}-{end}",
        )
    except Exception:
        return None
    mds = glob.glob(os.path.join(out_dir, "*.md"))
    return mds[0] if mds else None


def fallback_pymupdf(pdf_path, page_num, out_path):
    if fitz is None:
        return None
    try:
        with fitz.open(pdf_path) as doc:
            text = doc.load_page(page_num - 1).get_text("text")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        return out_path
    except Exception:
        log.exception(f"PyMuPDF fallback 실패: {pdf_path} p{page_num}")
        return None


def cleanup(raw_path, clean_path):
    with open(raw_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r"!\[.*?\]\(.*?\)", "", content, flags=re.DOTALL)
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


def process_pdf(pdf_path, work_dir, chunk_size=50, keep_chunks=False):
    """단일 PDF 처리. 결과 MD는 PDF 옆에 저장."""
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.dirname(os.path.abspath(pdf_path))
    out_md = os.path.join(out_dir, f"{base}.md")
    raw_md = os.path.join(out_dir, f"{base}.raw.md")
    fallback_report = os.path.join(out_dir, f"{base}.FALLBACK.txt")
    chunks_dir = os.path.join(work_dir, base)

    log.info(f"=== {os.path.basename(pdf_path)} ===")

    total = get_page_count(pdf_path)
    log.info(f"  총 페이지: {total}")

    if os.path.exists(chunks_dir):
        shutil.rmtree(chunks_dir)
    os.makedirs(chunks_dir)

    pending = [(s, min(s + chunk_size - 1, total)) for s in range(1, total + 1, chunk_size)]
    successful = []
    fallback_pages = []
    permanent_failures = []

    while pending:
        start, end = pending.pop(0)
        label = f"p{start:04d}-{end:04d}"
        chunk_dir = os.path.join(chunks_dir, label)
        t0 = time.time()
        md = extract_chunk(pdf_path, start, end, chunk_dir)
        if md:
            log.info(f"  {label} OK {time.time()-t0:.1f}s {os.path.getsize(md):>7}B")
            successful.append((start, md))
            continue

        log.warning(f"  {label} FAIL after {time.time()-t0:.1f}s — 분할")
        size = end - start + 1
        if size > 10:
            for s2 in range(start, end + 1, 10):
                pending.append((s2, min(s2 + 9, end)))
        elif size > 1:
            for p in range(start, end + 1):
                pending.append((p, p))
        else:
            p = start
            fb_md = os.path.join(chunks_dir, f"p{p:04d}_fallback.md")
            if fallback_pymupdf(pdf_path, p, fb_md):
                log.info(f"  p{p:04d} PyMuPDF fallback OK")
                successful.append((p, fb_md))
                fallback_pages.append(p)
            else:
                log.error(f"  p{p:04d} 어떤 방법으로도 복구 실패")
                permanent_failures.append(p)

    successful.sort(key=lambda x: x[0])

    with open(raw_md, "w", encoding="utf-8") as fout:
        for _, md in successful:
            with open(md, "r", encoding="utf-8") as fin:
                fout.write(fin.read())
                fout.write("\n")
    log.info(f"  raw -> {raw_md} ({os.path.getsize(raw_md)}B)")

    n_lines = cleanup(raw_md, out_md)
    log.info(f"  cleaned -> {out_md} ({os.path.getsize(out_md)}B / {n_lines} lines)")

    if fallback_pages or permanent_failures:
        with open(fallback_report, "w", encoding="utf-8") as f:
            if fallback_pages:
                f.write(f"PyMuPDF fallback 사용 페이지: {fallback_pages}\n")
            if permanent_failures:
                f.write(f"복구 실패 페이지(누락): {permanent_failures}\n")
        log.info(f"  보고서 -> {fallback_report}")
    elif os.path.exists(fallback_report):
        os.remove(fallback_report)

    if not keep_chunks:
        shutil.rmtree(chunks_dir, ignore_errors=True)


def find_pdfs(path):
    if os.path.isfile(path):
        return [path] if path.lower().endswith(".pdf") else []
    pdfs = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


def main():
    parser = argparse.ArgumentParser(description="PDF -> Markdown 안전 변환")
    parser.add_argument("input", help="PDF 파일 또는 PDF가 들어있는 디렉터리")
    parser.add_argument("--chunk-size", type=int, default=50, help="초기 청크 크기 (페이지 수, 기본 50)")
    parser.add_argument("--work-dir", default=None, help="중간 청크 작업 디렉터리 (기본: .work/)")
    parser.add_argument("--keep-chunks", action="store_true", help="중간 청크 보존 (디버그용)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    inp = os.path.abspath(args.input)
    pdfs = find_pdfs(inp)
    if not pdfs:
        sys.exit(f"PDF가 없습니다: {inp}")

    work_dir = os.path.abspath(args.work_dir) if args.work_dir else os.path.join(os.getcwd(), ".work")
    os.makedirs(work_dir, exist_ok=True)

    log.info(f"처리 대상 PDF: {len(pdfs)}개")
    for pdf in pdfs:
        try:
            process_pdf(pdf, work_dir, chunk_size=args.chunk_size, keep_chunks=args.keep_chunks)
        except Exception:
            log.exception(f"실패: {pdf}")


if __name__ == "__main__":
    main()
