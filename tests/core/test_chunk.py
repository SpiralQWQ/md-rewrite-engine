# -*- coding: utf-8 -*-
"""core/chunk 单元测试：切块 / 重叠 / 面包屑 / 超长行。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.core.assemble import assemble  # noqa: E402
from md_rewrite_engine.core.chunk import chunk_blocks  # noqa: E402


class TestChunk(unittest.TestCase):
    def test_small_single(self):
        md = "# 标题\n\n## 小节\n\n内容。\n"
        chunks = chunk_blocks(assemble(md), max_chars=8000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["breadcrumb"][0], "标题")

    def test_multi_chunk_overlap(self):
        md = "# 大文档\n" + "".join(f"## 节{i}\n\n第{i}节" + "很长的内容" * 20 + "\n\n" for i in range(10))
        chunks = chunk_blocks(assemble(md), max_chars=800, overlap_chars=50)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(all(len(c["text"]) <= 850 for c in chunks), True)
        self.assertTrue(any(c["overlap"] for c in chunks))

    def test_first_chunk_no_overlap(self):
        md = "# 大\n" + "".join(f"## 节{i}\n\n" + "x" * 200 + "\n" for i in range(8))
        chunks = chunk_blocks(assemble(md), max_chars=500, overlap_chars=50)
        self.assertFalse(chunks[0]["overlap"])

    def test_super_long_single_line(self):
        huge = assemble("# 超长\n\n" + "很长的内容" * 200 + "\n")
        chunks = chunk_blocks(huge, max_chars=300, overlap_chars=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c["text"]) <= 320 for c in chunks))

    def test_empty(self):
        self.assertEqual(chunk_blocks([], max_chars=300), [])

    # ── A2 段落边界切（Task-01/02）──

    def test_no_heading_para_boundary(self):
        """无标题流水账：按段落边界切，每块整段结尾（不切半句）。"""
        md = "\n\n".join(f"段落{i}。内容丰富。" * 50 for i in range(6))
        chunks = chunk_blocks(assemble(md), max_chars=800)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertTrue(c["text"].rstrip().endswith("。"))

    def test_single_overlong_para_hard_split(self):
        """单段超长（>max_chars）：才字符硬切兜底，每块 ≤ max_chars。"""
        md = "超长段落内容。" * 500
        chunks = chunk_blocks(assemble(md), max_chars=800, overlap_chars=0)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c["text"]), 800)

    def test_heading_regression(self):
        """有标题 md：仍按标题边界切（回归不破坏）。"""
        md = "# 根\n\n## 甲\n\n正文甲。\n\n## 乙\n\n正文乙。\n"
        chunks = chunk_blocks(assemble(md), max_chars=800)
        self.assertEqual(chunks[0]["breadcrumb"][0], "根")

    def test_para_exact_max(self):
        """段落恰等于 max_chars：不硬切，整段保留。"""
        md = "界" * 800
        chunks = chunk_blocks(assemble(md), max_chars=800, overlap_chars=0)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]["text"]), 800)

    def test_consecutive_blank_lines(self):
        """连续空行：不崩，正确分组（段落边界可合并）。"""
        md = "段落甲。\n\n\n\n段落乙。\n\n\n段落丙。"
        chunks = chunk_blocks(assemble(md), max_chars=800)
        joined = "".join(c["text"] for c in chunks)
        self.assertIn("段落甲", joined)
        self.assertIn("段落乙", joined)
        self.assertIn("段落丙", joined)

    def test_empty_and_whitespace(self):
        """空 / 纯空白输入：返回空列表。"""
        self.assertEqual(chunk_blocks(assemble(""), max_chars=300), [])
        self.assertEqual(chunk_blocks(assemble("   \n\n  "), max_chars=300), [])


if __name__ == "__main__":
    unittest.main()
