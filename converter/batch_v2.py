#!/usr/bin/env python3
"""과목별 교과서 폴더에서 md가 없는 PDF를 convert_v2로 PDF 옆에 변환한다.

한 쪽씩 보이는 PDF와 2쪽 펼침 PDF(좌·우 반쪽으로 나눔)를 변환하고, 글자 깨짐·글자 없음(스캔)은 건너뛰고 목록에 남긴다.
이미 같은 이름의 md나 *_split 폴더가 있으면 건드리지 않는다.
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import fitz

from convert_v2 import convert, spread_mode

ROOT = Path.home() / "Library/CloudStorage/GoogleDrive-tgtec26@snu-g.ms.kr/내 드라이브/02_교과서 자료/과목별 교과서"
REPORT = Path(__file__).parent / "drive_work/batch_v2_report.jsonl"


def already_done(pdf: Path) -> bool:
    return pdf.with_suffix(".md").exists() or (pdf.parent / f"{pdf.stem}_split").exists()


def sample_text(doc) -> str:
    """책 전체에서 고르게 12쪽을 뽑는다(앞쪽 표지·차례만 보고 판정하지 않도록)."""
    n = len(doc)
    return "".join(doc[i].get_text() for i in sorted({int(k * (n - 1) / 11) for k in range(12)}))


def garbled(text: str) -> bool:
    """읽을 수 있는 한글이 거의 없고 대체·사용자 영역 문자가 많으면 글자 깨짐으로 본다."""
    body = [ch for ch in text if not ch.isspace()]
    hangul = sum("\uac00" <= ch <= "\ud7a3" for ch in body)
    bad = sum(ch == "\ufffd" or "\ue000" <= ch <= "\uf8ff" for ch in body)
    return len(body) > 200 and (hangul / len(body) < 0.25 or bad / len(body) > 0.15)


def work(pdf_str: str) -> dict:
    pdf = Path(pdf_str)
    rec = {"pdf": str(pdf.relative_to(ROOT))}
    try:
        doc = fitz.open(pdf)
        rec["pages"] = len(doc)
        rec["spread"] = spread_mode(doc)
        text = sample_text(doc)
        if len(text.strip()) < 80 * min(len(doc), 12) * 0.2:
            return {**rec, "status": "skip", "why": "글자 거의 없음(스캔 추정)"}
        if garbled(text):
            return {**rec, "status": "skip", "why": "글자 깨짐"}
        doc.close()
        md, report = convert(pdf)
        out = pdf.with_suffix(".md")
        if out.exists():
            return {**rec, "status": "skip", "why": "md 이미 있음"}
        out.write_text(md, encoding="utf-8")
        return {**rec, "status": "ok", "audit": report["audit_mismatch"], "review": report["review_pages"],
                "unlabeled": len(report["unlabeled_pages"])}
    except Exception as e:  # noqa: BLE001 - 한 권 실패가 전체를 멈추지 않게
        return {**rec, "status": "error", "why": f"{type(e).__name__}: {e}"}


def main():
    pdfs = sorted(p for p in ROOT.rglob("*.pdf") if not already_done(p))
    print(f"변환 대상 {len(pdfs)}권", flush=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=4) as ex, REPORT.open("a", encoding="utf-8") as log:
        for i, rec in enumerate(ex.map(work, map(str, pdfs)), 1):
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log.flush()
            if i % 25 == 0:
                print(f"{i}/{len(pdfs)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
