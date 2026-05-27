# Reproducible Local Conversion

직장 Mac Studio처럼 로컬에 PDF가 많은 환경을 기준으로 한다.

## 고정 기준

같은 결과를 내려면 다음이 같아야 한다.

- Git commit
- `requirements.txt` 패키지 버전
- OpenJDK 설치 상태
- 원본 PDF 파일 checksum
- `UNIT_CONFIG` 단원 시작 페이지 설정
- 공통 후처리 규칙

현재 검증 기준:

- PyMuPDF `1.27.2.3`
- OpenDataLoader PDF `2.4.6`
- OpenDataLoader는 Markdown이 아니라 JSON `content`/`bounding box`를 사용한다.

## Mac Studio 최초 세팅

```sh
git clone https://github.com/tgtec26-crypto/textbook-pdf-md-converter.git
cd textbook-pdf-md-converter
./setup_mac.sh
```

매번 작업 전:

```sh
cd textbook-pdf-md-converter
git pull
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
. .venv-opendataloader/bin/activate
```

## 로컬 PDF 폴더 구조

권장:

```text
/Volumes/Textbooks/pdf/
  과학/
    미래엔_중학교_과학2_김태일_교과서.pdf
  역사/
    비상_중학교_역사1_이병인_교과서.pdf
```

과목 폴더가 없으면 `_unsorted`로 저장된다.

## 변환 실행

```sh
python convert_local.py \
  --input "/Volumes/Textbooks/pdf" \
  --output "/Volumes/Textbooks/output_md" \
  --reports "/Volumes/Textbooks/reports" \
  --clean-output
```

이어하기:

```sh
python convert_local.py \
  --input "/Volumes/Textbooks/pdf" \
  --output "/Volumes/Textbooks/output_md" \
  --reports "/Volumes/Textbooks/reports" \
  --start-at "역사/비상_중학교_역사1_이병인_교과서"
```

## 결과 위치

```text
output_md/
  과목/
    PDF파일명/
      PDF파일명.md
      units/
        01_대단원명_시작-끝.md

reports/
  environment.json
  pdf_checksums.tsv
  local_summary.json
  local_과목_PDF파일명.json
```

`pdf_checksums.tsv`가 핵심이다. 다른 기기와 결과가 다르면 먼저 checksum부터 비교한다.

## 검증

총 단원 파일 수:

```sh
find "/Volumes/Textbooks/output_md" -path '*/units/*.md' | wc -l
```

빈줄 검사:

```sh
python - <<'PY'
from pathlib import Path
root = Path("/Volumes/Textbooks/output_md")
bad = []
for p in sorted(root.glob("*/*/units/*.md")):
    blanks = sum(1 for line in p.read_text(encoding="utf-8").splitlines() if not line.strip())
    if blanks:
        bad.append((blanks, p))
print("blank_issues", len(bad))
for item in bad[:20]:
    print(item)
PY
```

환경 기록 확인:

```sh
cat "/Volumes/Textbooks/reports/environment.json"
```

## 결과가 다를 때 보는 순서

1. `git rev-parse HEAD`
2. `cat reports/environment.json`
3. `diff` 또는 checksum 비교
4. PDF 파일명과 `reports/pdf_checksums.tsv`
5. 해당 교과서가 `UNIT_CONFIG`에 있는지 확인

파일명이 `UNIT_CONFIG`와 다르면 단원 분할은 전체 1개 파일로 떨어진다. 이 경우 PDF stem 이름에 맞춰 `run_drive_conversion.py`의 `UNIT_CONFIG`를 추가한다.
