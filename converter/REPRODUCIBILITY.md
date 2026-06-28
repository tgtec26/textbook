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

한 줄 실행:

```sh
./run_local_conversion.sh \
  "/Volumes/Textbooks/pdf" \
  "/Volumes/Textbooks/output_md" \
  "/Volumes/Textbooks/reports"
```

기존 결과를 지우지 않고 실행:

```sh
./run_local_conversion.sh \
  "/Volumes/Textbooks/pdf" \
  "/Volumes/Textbooks/output_md" \
  "/Volumes/Textbooks/reports" \
  --keep-output
```

직접 실행:

```sh
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
. .venv-opendataloader/bin/activate
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

## AI에게 맡기는 법

직장 Mac Studio에서 Codex, Claude Code 같은 AI가 터미널을 사용할 수 있으면 직접 명령을 칠 필요 없다.

AI에게 아래처럼 요청한다.

```text
이 저장소에서 로컬 교과서 PDF 변환 작업을 실행해줘.
PDF 원본 폴더는 "/Volumes/Textbooks/pdf"이고,
결과는 "/Volumes/Textbooks/output_md"에 저장해줘.
리포트는 "/Volumes/Textbooks/reports"에 저장해줘.
REPRODUCIBILITY.md 절차를 따라 환경 확인 후 실행해줘.
기존 결과는 지워도 돼.
```

AI에게 꼭 알려줄 것:

- PDF 원본 폴더
- 결과 저장 폴더
- 리포트 저장 폴더
- 기존 결과를 지워도 되는지
- 변환 후 코드 변경을 GitHub에 push할지

AI가 해야 할 일:

- `git pull`
- 필요하면 `./setup_mac.sh`
- `./run_local_conversion.sh "<PDF폴더>" "<결과폴더>" "<리포트폴더>"`
- 결과 파일 수 확인
- `reports/pdf_checksums.tsv` 생성 확인
- 빈줄 검사
- 실패 PDF가 있으면 원인 보고

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
