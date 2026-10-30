"""convert_v2.py 회귀 테스트: 합성 PDF로 줄바꿈 잇기, 보조단 분리, 그림 속 글자 분리를 확인한다."""
import tempfile
import unittest
from pathlib import Path

import fitz

from convert_v2 import convert, spread_mode


def justify(text: str, width: float = 330.0, size: float = 10.7) -> str:
    """실제 교과서처럼 줄 오른쪽 끝이 맞도록 낱말 사이 공백을 늘린다(줄 끝 공백은 그대로 둔다)."""
    tail = " " if text.endswith(" ") else ""
    core = text.rstrip(" ")
    k = 0
    while fitz.get_text_length(core + tail, fontname="korea", fontsize=size) < width - 4:
        gaps = [j for j, ch in enumerate(core) if ch == " "]
        i = gaps[k % len(gaps)]
        core = core[:i] + " " + core[i:]
        k += 1
    return core + tail


def make_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page(width=624, height=794)
    f = dict(fontname="korea", fontsize=10.7)
    # 본문 단(x 85~431): 낱말 중간에서 줄바꿈된 문단 + 줄 끝 공백이 남은 문단
    body = [
        (justify("서부 아프리카의 해안 지역에는 자원 개발과 경제활동"), 120),
        (justify("이 활발한 나이지리아, 코트디부아르 등 여러 국"), 141),
        ("가가 위치한다. 라고스는 인구가 많은 대도시이다.", 162),
        (justify("동부 아프리카는 기온이 선선하여 과거부터 많은 고원 지역이 "), 200),
        ("있다. 에티오피아의 수도는 아디스아바바이다.", 221),
    ]
    for text, y in body:
        page.insert_text((85, y), text, **f)
    # 보조단(x 457~): 본문 단 바깥
    for i, text in enumerate(["에스파냐어로 하얀 집을 뜻하는", "모로코의 카사블랑카", "고릴라 서식지가 있는 열대"]):
        page.insert_text((457, 130 + i * 20), text, fontname="korea", fontsize=8.1)
    # 지도: 큰 도형 안에 짧은 지명 여러 개
    page.draw_rect(fitz.Rect(85, 400, 400, 600), color=(0, 0, 0), fill=(0.9, 0.8, 0.6))
    for i, name in enumerate(["카이로", "라고스", "나이로비", "킨샤사", "케이프타운", "다카르"]):
        page.insert_text((100 + (i % 3) * 100, 450 + (i // 3) * 60), name, fontname="korea", fontsize=6)
    page.insert_text((490, 745), "73", fontname="korea", fontsize=8)
    doc.save(path)


class ConvertV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        pdf = Path(cls.tmp.name) / "t.pdf"
        make_pdf(pdf)
        cls.md, cls.report = convert(pdf)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_wrapped_lines_join_without_space_in_a_word(self):
        self.assertIn("경제활동이 활발한", self.md)

    def test_wrapped_lines_join_mid_word_across_three_lines(self):
        self.assertIn("여러 국가가 위치한다.", self.md)

    def test_trailing_space_in_pdf_keeps_word_gap(self):
        self.assertIn("고원 지역이 있다.", self.md)

    def test_side_column_is_separate_section(self):
        main, _, side = self.md.partition("### 보조단")
        self.assertIn("카사블랑카", side)
        self.assertNotIn("카사블랑카", main)

    def test_map_labels_move_to_figure_section(self):
        main = self.md.split("### 그림 속 글자")[0]
        figure = self.md.split("### 그림 속 글자")[1]
        self.assertIn("케이프타운", figure)
        self.assertNotIn("케이프타운", main)

    def test_page_number_from_footer(self):
        self.assertIn("## 73쪽", self.md)

    def test_no_chars_lost_or_duplicated(self):
        self.assertEqual(self.report["audit_mismatch"], {})


def make_spread_pdf(path: Path):
    """가로로 긴 쪽(2쪽 펼침) 2장 + 세로 표지 1장: 왼쪽 반이 34·36쪽, 오른쪽 반이 35·37쪽이다."""
    doc = fitz.open()
    doc.new_page(width=624, height=794)
    for left, right in ((34, 35), (36, 37)):
        page = doc.new_page(width=1248, height=794)
        for k, (n, name) in enumerate(((left, "왼쪽"), (right, "오른쪽"))):
            x = 85 + k * 624
            for i in range(6):
                page.insert_text((x, 120 + i * 21), f"{name} {n}쪽 본문 문장 {i} 입니다 가나다라마바사", fontname="korea", fontsize=10.7)
            page.insert_text((x + 380, 745), str(n), fontname="korea", fontsize=8)
    doc.save(path)


class SpreadTest(unittest.TestCase):
    def test_spread_pdf_splits_into_left_and_right_pages_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "s.pdf"
            make_spread_pdf(pdf)
            doc = fitz.open(pdf)
            self.assertTrue(spread_mode(doc))
            md, report = convert(pdf)
        self.assertTrue(report["spread"])
        heads = [md.index(f"## {n}쪽") for n in (34, 35, 36, 37)]
        self.assertEqual(heads, sorted(heads))
        left, right = md.split("## 35쪽")[0], md.split("## 35쪽")[1].split("## 36쪽")[0]
        self.assertIn("왼쪽 34쪽", left)
        self.assertNotIn("오른쪽", left)
        self.assertIn("오른쪽 35쪽", right)
        self.assertNotIn("왼쪽", right)

    def test_single_wide_cover_is_not_a_spread(self):
        doc = fitz.open()
        doc.new_page(width=1248, height=794)
        for _ in range(5):
            doc.new_page(width=624, height=794)
        self.assertFalse(spread_mode(doc))


class PageLabelTest(unittest.TestCase):
    def test_bare_number_wins_over_numbered_section_title_in_footer(self):
        # 단원 첫 펼침 2쪽은 번호가 없고, 셋째 쪽 하단에는 쪽 번호와 "01 중단원" 머리말이 함께 있다
        doc = fitz.open()
        for _ in range(2):
            doc.new_page(width=624, height=794).insert_text((85, 120), "단원 도입", fontname="korea", fontsize=10.7)
        page = doc.new_page(width=624, height=794)
        page.insert_text((85, 120), "본문", fontname="korea", fontsize=10.7)
        page.insert_text((60, 752), "01 유전자발현 과정", fontname="korea", fontsize=7)
        page.insert_text((540, 760), "57", fontname="korea", fontsize=8)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "label.pdf"
            doc.save(pdf)
            md, _ = convert(pdf)
        self.assertEqual([l for l in md.splitlines() if l.startswith("## ")], ["## 55쪽", "## 56쪽", "## 57쪽"])


if __name__ == "__main__":
    unittest.main()
