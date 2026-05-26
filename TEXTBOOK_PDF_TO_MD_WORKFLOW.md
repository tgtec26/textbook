# Textbook PDF to Markdown Workflow

이 문서는 다른 Mac에서 같은 작업을 재현하기 위한 절차이다.

## 목표

- Google Drive 과목 폴더 안 기존 Markdown 파일 삭제
- PDF 교과서 16권을 대단원별 Markdown으로 변환
- 1쪽짜리 PDF와 2쪽 펼침 PDF 자동 판정
- PyMuPDF 텍스트가 깨지는 PDF는 OpenDataLoader PDF로 재시도
- 결과 Markdown을 각 교과서별 `_split` 폴더에 업로드

## 준비물

- macOS + Homebrew
- Python 3
- Google Drive 접근 가능한 `gws` CLI
- Google Drive 로그인/인증 완료 상태

현재 작업 폴더 기준:

```sh
/Users/choijonghun/Documents/textbook2
```

## 설치

Java와 OpenDataLoader PDF 설치:

```sh
brew install openjdk
python3 -m venv .venv-opendataloader
. .venv-opendataloader/bin/activate
pip install opendataloader-pdf
```

역사 PDF 일부 예외 페이지를 OCR로 보정해야 할 때만 Tesseract 설치:

```sh
brew install tesseract tesseract-lang
```

## 주요 파일

- `run_drive_conversion.py`
  - 최종 변환/분할/업로드 스크립트
  - PyMuPDF 실패 감지 후 OpenDataLoader 재시도
  - 대단원 시작 페이지 규칙 포함

- `process_drive_textbooks.py`
  - Google Drive 인벤토리, PDF 다운로드, Markdown 삭제 함수 보유
  - 예전 자동 변환 로직도 있으므로 `python3 process_drive_textbooks.py` 직접 실행은 피한다.

- `drive_file_manifest.tsv`
  - PDF/기존 MD 파일 ID 목록

- `drive_work/pdfs`
  - 원본 PDF 저장 위치

- `drive_work/outputs`
  - 변환된 전체 Markdown 및 대단원별 Markdown

- `drive_work/reports/final_summary.json`
  - 최종 변환 보고서

## Google Drive 폴더 ID

`run_drive_conversion.py`와 `process_drive_textbooks.py` 안에 과목 폴더 ID가 들어 있다.

```python
SUBJECT_FOLDERS = {
    "과학": "...",
    "국어": "...",
    "도덕": "...",
    "사회": "...",
    "수학": "...",
    "역사": "...",
    "영어": "...",
}
```

다른 Drive 폴더에서 작업할 때는 이 값을 먼저 바꾼다.

## PDF 다운로드

이미 `drive_work/pdfs`가 있으면 생략 가능.

새 Mac에서 Drive에서 다시 받을 때:

```sh
python3 - <<'PY'
from pathlib import Path
from process_drive_textbooks import inventory, download_pdfs

Path("drive_work/pdfs").mkdir(parents=True, exist_ok=True)
download_pdfs(inventory())
PY
```

## 변환 실행

전체 실행:

```sh
python3 run_drive_conversion.py
```

특정 교과서부터 이어서 실행:

```sh
SKIP_TRASH=1 START_AT='역사/비상_중학교_역사1_이병인_교과서' python3 run_drive_conversion.py
```

`START_AT` 형식:

```text
과목/PDF파일명에서 .pdf를 뺀 이름
```

예:

```text
국어/천재_중학교_국어2-1_노미숙_교과서
```

## 변환 방식

기본:

- PyMuPDF로 페이지 폭/높이 확인
- 2쪽 펼침이면 좌/우를 논리 페이지로 분리
- 하단 페이지 번호 샘플로 offset 산출
- 본문을 Markdown으로 저장

깨짐 감지:

- 앞쪽 20쪽 텍스트에서 비정상 문자가 많으면 실패로 판정
- 이 경우 OpenDataLoader PDF로 재변환
- 현재 역사1, 역사2가 이 경로를 사용한다.

OpenDataLoader:

- 전체 변환 실패 가능성이 있어 40쪽 단위로 나눠 실행
- 실패 묶음은 반으로 쪼개 재시도
- 끝까지 실패하는 단일 페이지만 PyMuPDF fallback 표시

공통 후처리:

- PyMuPDF와 OpenDataLoader 결과 모두 `clean_text()`를 마지막에 통과한다.
- 빈줄은 전부 제거한다.
- 한 줄에 한글 한 글자만 있는 줄은 제거한다.
- `.indd` 같은 제작 파일명 줄은 제거한다.
- 페이지 제목 바로 아래의 단독 숫자 노이즈를 제거한다.
- 이 후처리는 엔진별로 다르게 적용하지 않는다.

## 대단원 분할

대단원 시작 기준은 `run_drive_conversion.py`의 `UNIT_CONFIG`에 있다.

차례에는 보통 첫 소단원 시작 페이지만 있으므로, 스크립트는 그 앞뒤를 확인해 대단원 도입 페이지를 찾는다.

예:

```python
"비상_중학교_역사1_이병인_교과서": [
    ("역사 학습의 기초", 9),
    ("문명의 발생과 고대 세계의 형성", 27),
]
```

위 숫자는 차례의 첫 소단원 시작 페이지이고, 실제 대단원 파일은 그보다 앞쪽 도입 페이지부터 시작할 수 있다.

## 업로드

각 PDF마다 Drive 과목 폴더 아래에 다음 형식의 폴더를 만든다.

```text
PDF파일명_split
```

그 안에 대단원별 Markdown을 업로드한다.

이미 같은 이름의 Markdown이 있으면 작업 전에 휴지통 처리한다.

## 검산

로컬 대단원 파일 수:

```sh
find drive_work/outputs -path '*/units/*.md' | wc -l
```

Drive 활성 Markdown 수:

```sh
python3 - <<'PY'
from process_drive_textbooks import inventory, MD_MIME
items = inventory()
md = [x for x in items if x.mime_type == MD_MIME or x.name.endswith(".md")]
print(len(md))
PY
```

최종 요약:

```sh
python3 - <<'PY'
from pathlib import Path
import json

for p in sorted(Path("drive_work/reports").glob("final_*_*.json")):
    d = json.loads(p.read_text())
    if isinstance(d, dict):
        print(d["subject"], d["pdf"], d["engine"], d["unit_count"])
PY
```

## 현재 완료 결과

- 총 PDF: 16권
- 총 대단원 Markdown: 106개
- Drive 활성 Markdown: 106개

과목별:

- 과학 15개
- 국어 16개
- 도덕 8개
- 사회 24개
- 수학 12개
- 역사 13개
- 영어 18개

엔진:

- PyMuPDF: 과학, 국어, 도덕, 사회, 수학, 영어
- OpenDataLoader PDF: 역사1, 역사2

## 예외 처리 기록

- 역사1: 앞부분 3쪽 OpenDataLoader 실패. 대단원 파일에는 포함되지 않음.
- 역사2: 54쪽 OpenDataLoader 실패. 이미지 확인 및 OCR 보조로 해당 페이지를 수동 보정했고, `02_통일 신라와 발해_39-66.md`를 다시 업로드함.
- 2026-05-27: 역사 Markdown 빈줄 제거 누락 수정. 이후 모든 엔진 결과는 같은 `clean_text()` 후처리를 사용함.

## 주의

- `process_drive_textbooks.py`는 직접 실행하지 않는다.
- 재실행 전 Drive에 이미 정상 Markdown이 있으면 `SKIP_TRASH=1`을 쓰지 않는다.
- 중간 실패 뒤 이어서 실행할 때만 `SKIP_TRASH=1 START_AT=...`를 사용한다.
- `UNIT_CONFIG`를 바꾸면 해당 교과서 `_split` 폴더의 기존 Markdown을 휴지통 처리하고 다시 업로드해야 한다.
