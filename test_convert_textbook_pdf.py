import tempfile
import unittest
from pathlib import Path

from convert_textbook_pdf import convert, lines_to_markdown


PDF = Path("/Users/choijonghun/Downloads/미래엔_중학교_과학2_김태일_교과서.pdf")


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


if __name__ == "__main__":
    unittest.main()
