# 교과서 PDF Markdown 변환기

교과서 PDF를 대단원별 Markdown 파일로 변환하는 작업 도구입니다.

## 구성

- `convert_local.py`: Mac Studio나 외장 드라이브의 로컬 PDF 폴더를 변환하는 스크립트
- `run_local_conversion.sh`: 로컬 변환을 한 줄로 실행하는 스크립트
- `setup_mac.sh`: 새 Mac 작업 환경 세팅 스크립트
- `requirements.txt`: Python 패키지 버전 고정 파일
- `run_drive_conversion.py`: Google Drive 기반 변환/분할/업로드 스크립트
- `process_drive_textbooks.py`: Google Drive 파일 목록, 다운로드, 삭제 보조 함수
- `convert_textbook_pdf.py`: 초기 2쪽 펼침 PDF 변환 보조 스크립트
- `test_convert_textbook_pdf.py`: 회귀 테스트
- `REPRODUCIBILITY.md`: 로컬 작업 환경 세팅과 재현 절차
- `TEXTBOOK_PDF_TO_MD_WORKFLOW.md`: Google Drive 기반 작업 절차

## 저장소에 포함하지 않는 것

원본 PDF, 변환된 Markdown 교과서, Google Drive manifest, 로컬 리포트는 `.gitignore`로 제외합니다.

이 파일들은 저작권이 있는 교과서 내용이나 개인 Drive ID를 포함할 수 있습니다.

## 빠른 시작

처음 한 번:

```sh
./setup_mac.sh
```

로컬 PDF 변환:

```sh
./run_local_conversion.sh "/path/to/pdf_root" "/path/to/output_md" "/path/to/reports"
```

예:

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

## AI에게 맡기는 법

직장 Mac Studio에서 Codex, Claude Code 같은 AI가 터미널을 사용할 수 있으면 아래처럼 요청하면 됩니다.

```text
이 저장소에서 로컬 교과서 PDF 변환 작업을 실행해줘.
PDF 원본 폴더는 "/Volumes/Textbooks/pdf"이고,
결과는 "/Volumes/Textbooks/output_md"에 저장해줘.
리포트는 "/Volumes/Textbooks/reports"에 저장해줘.
REPRODUCIBILITY.md 절차를 따라 환경 확인 후 실행해줘.
기존 결과는 지워도 돼.
```

## 자세한 문서

- 로컬 Mac Studio 작업: [REPRODUCIBILITY.md](REPRODUCIBILITY.md)
- Google Drive 기반 작업: [TEXTBOOK_PDF_TO_MD_WORKFLOW.md](TEXTBOOK_PDF_TO_MD_WORKFLOW.md)
