import json
import tempfile
import unittest
from pathlib import Path

import fitz

from convert_local import conversion_groups, donga_middle_science_part, list_pdfs
from convert_textbook_pdf import convert, lines_to_markdown
from convert_yellow_auto_groups import candidate_output_path, load_auto_candidates
from group_yellow_sources import parse_split_identity
from process_drive_textbooks import crop_textbook_page_to_md
from run_drive_conversion import clean_text, opendataloader_physical_page_to_chunks


PDF = Path(__file__).parent.parent / "textbook/서울사대부여중/과학/미래엔_중학교_과학2_김태일_교과서.pdf"
VISANG_SCIENCE2 = Path(__file__).parent.parent / "textbook/출판사_비상/중학교/과학/비상_중학교_과학2_임태훈_교과서.pdf"


class TextbookConversionTest(unittest.TestCase):
    def convert_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sample.md"
            convert(PDF, out, offset=-2, start_physical=104, end_physical=104)
            return out.read_text(encoding="utf-8")

    def test_removes_figure_labels_and_speech_bubbles(self):
        md = self.convert_sample()
        unwanted = [
            "녹말 넌",
            "나는 들어갈",
            "수 없어.",
            "통과!",
            "\n입\n",
            "\n침샘\n",
            "\n식도\n",
            "\n쓸개\n",
            "\n이자\n",
            "\n항문\n",
            "\n그림 VI-3",
            "4 아이오딘",
        ]
        for text in unwanted:
            self.assertNotIn(text, md)

    def test_collapses_repeated_blank_lines(self):
        md = self.convert_sample()
        self.assertNotIn("\n\n", md)

    def test_removes_single_korean_character_lines(self):
        md = lines_to_markdown(
            [
                {"text": "정상 문장", "x0": 0, "x1": 50, "y0": 0, "y1": 10},
                {"text": "가", "x0": 0, "x1": 10, "y0": 30, "y1": 40},
                {"text": "A", "x0": 0, "x1": 10, "y0": 60, "y1": 70},
            ]
        )
        self.assertIn("정상 문장", md)
        self.assertNotIn("\n가\n", f"\n{md}\n")
        self.assertIn("\nA\n", f"\n{md}\n")

    def test_one_up_textbook_page_moves_helper_column_after_main_column(self):
        page = fitz.open(VISANG_SCIENCE2)[16]
        md = crop_textbook_page_to_md(page)

        self.assertIn("### 보조단", md)
        self.assertLess(md.index("4. 측정"), md.index("### 보조단"))
        self.assertLess(md.index("### 보조단"), md.index("준비물| 질산 칼륨"))
        self.assertLess(md.index("### 보조단"), md.index("다르게 해 보기"))
        self.assertNotIn("\n017", f"\n{md}")

    def test_opendataloader_two_up_page_splits_sides_and_moves_helper_columns(self):
        rect = fitz.Rect(0, 0, 1000, 800)
        items = [
            {"page number": 1, "bounding box": [60, 100, 130, 120], "content": "왼쪽 보조"},
            {"page number": 1, "bounding box": [210, 100, 470, 120], "content": "왼쪽 본문"},
            {"page number": 1, "bounding box": [530, 100, 780, 120], "content": "오른쪽 본문"},
            {"page number": 1, "bounding box": [860, 100, 950, 120], "content": "오른쪽 보조"},
        ]

        chunks = opendataloader_physical_page_to_chunks(items, rect, "two-up", 0, 1)

        self.assertEqual([logical for logical, _ in chunks], [2, 3])
        left_md = chunks[0][1]
        right_md = chunks[1][1]
        self.assertLess(left_md.index("왼쪽 본문"), left_md.index("### 보조단"))
        self.assertLess(left_md.index("### 보조단"), left_md.index("왼쪽 보조"))
        self.assertNotIn("오른쪽", left_md)
        self.assertLess(right_md.index("오른쪽 본문"), right_md.index("### 보조단"))
        self.assertLess(right_md.index("### 보조단"), right_md.index("오른쪽 보조"))
        self.assertNotIn("왼쪽", right_md)

    def test_opendataloader_one_up_page_keeps_single_logical_page_with_helper_column(self):
        rect = fitz.Rect(0, 0, 500, 800)
        items = [
            {"page number": 1, "bounding box": [40, 100, 140, 120], "content": "본문"},
            {"page number": 1, "bounding box": [380, 100, 470, 120], "content": "오른쪽 보조"},
        ]

        chunks = opendataloader_physical_page_to_chunks(items, rect, "one-up", 0, 1)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], 1)
        md = chunks[0][1]
        self.assertLess(md.index("본문"), md.index("### 보조단"))
        self.assertLess(md.index("### 보조단"), md.index("오른쪽 보조"))

    def test_donga_middle_science_groups_major_units_and_skips_subunits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            science = root / "출판사_동아" / "중학교" / "과학"
            science.mkdir(parents=True)
            major_1 = science / "동아_중학교_과학1_태양계_교과서.pdf"
            major_2 = science / "동아_중학교_과학1_열_교과서.pdf"
            subunit = science / "동아_중학교_과학1_태양계_7-1-1_교과서.pdf"
            other = science / "다른_교과서.pdf"
            for path in [major_1, major_2, subunit, other]:
                path.write_bytes(b"%PDF-1.4\n")

            groups = conversion_groups(root, sorted([major_1, major_2, subunit, other]))
            grouped_names = [[path.name for path in group] for group in groups]

        self.assertIn(["다른_교과서.pdf"], grouped_names)
        self.assertIn(["동아_중학교_과학1_열_교과서.pdf", "동아_중학교_과학1_태양계_교과서.pdf"], grouped_names)
        self.assertNotIn(["동아_중학교_과학1_태양계_7-1-1_교과서.pdf"], grouped_names)

    def test_donga_middle_science_part_detects_book_stem_and_title(self):
        path = Path("동아_중학교_과학2_물질의특성_1-1-1_교과서.pdf")
        part = donga_middle_science_part(path)

        self.assertEqual(part["book_stem"], "동아_중학교_과학2_교과서")
        self.assertEqual(part["title"], "물질의 특성")
        self.assertEqual(part["subunit"], "1-1-1")

    def test_list_pdfs_skips_symlinks_and_realpath_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            link = root / "link.pdf"
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest("symlink unavailable")

            pdfs = list_pdfs(root)

        self.assertEqual([path.name for path in pdfs], ["source.pdf"])

    def test_clean_text_drops_empty_page_sections(self):
        md = clean_text("# Book\n\n## 1쪽\n\n## 2쪽\n본문\n\n## 3쪽\n")

        self.assertNotIn("## 1쪽", md)
        self.assertIn("## 2쪽\n본문", md)
        self.assertNotIn("## 3쪽", md)

    def test_parse_split_identity_handles_common_yellow_patterns(self):
        numbered = parse_split_identity("동아_고등학교_과학탐구실험1_2단원_교과서.pdf")
        roman_sub = parse_split_identity("동아_고등학교_물리학_Ⅱ-03단원_교과서.pdf")
        roman_title = parse_split_identity("동아_중학교_도덕1_Ⅲ.사회공동체와의관계_교과서.pdf")
        subunit = parse_split_identity("동아_중학교_과학2_물질의특성_1-1-2_교과서.pdf")

        self.assertEqual(numbered["book_key"], "동아_고등학교_과학탐구실험1_교과서")
        self.assertEqual(numbered["order_key"], (2,))
        self.assertEqual(roman_sub["book_key"], "동아_고등학교_물리학_교과서")
        self.assertEqual(roman_sub["order_key"], (2, 3))
        self.assertEqual(roman_title["book_key"], "동아_중학교_도덕1_교과서")
        self.assertEqual(roman_title["order_key"], (3,))
        self.assertEqual(subunit["book_key"], "동아_중학교_과학2_교과서")
        self.assertEqual(subunit["order_key"], (1, 1, 2))

    def test_yellow_auto_loader_keeps_only_existing_multi_pdf_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            existing_a = root / "출판사_동아" / "고등학교" / "과학" / "a.pdf"
            existing_b = root / "출판사_동아" / "고등학교" / "과학" / "b.pdf"
            missing = root / "출판사_동아" / "고등학교" / "과학" / "missing.pdf"
            existing_a.parent.mkdir(parents=True)
            existing_a.write_bytes(b"%PDF-1.4\n")
            existing_b.write_bytes(b"%PDF-1.4\n")
            grouping = reports / "yellow_grouping_report.json"
            grouping.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "status": "auto_group_candidate",
                                "scope": "출판사_동아/고등학교/과학",
                                "book_key": "동아_고등학교_물리학_교과서",
                                "pdfs": [
                                    {"relative_path": str(existing_a.relative_to(root)), "unit_label": "Ⅰ단원"},
                                    {"relative_path": str(existing_b.relative_to(root)), "unit_label": "Ⅱ단원"},
                                    {"relative_path": str(missing.relative_to(root)), "unit_label": "Ⅲ단원"},
                                ],
                            },
                            {
                                "status": "needs_manual_review",
                                "scope": "출판사_동아/고등학교/과학",
                                "book_key": "manual",
                                "pdfs": [],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            candidates = load_auto_candidates(grouping, root)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(candidates[0]["pdfs"]), 2)

    def test_yellow_candidate_output_path_uses_publisher_subject_and_book_key(self):
        candidate = {
            "book_key": "동아_고등학교_물리학_교과서",
            "pdfs": [{"relative_path": "출판사_동아/고등학교/과학/동아_고등학교_물리학_Ⅰ단원_교과서.pdf"}],
        }

        path = candidate_output_path(Path("/out"), candidate)

        self.assertEqual(path, Path("/out/출판사_동아/동아_고등학교_물리학_교과서/동아_고등학교_물리학_교과서.md"))


if __name__ == "__main__":
    unittest.main()
