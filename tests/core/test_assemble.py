# -*- coding: utf-8 -*-
"""core/assemble 单元测试：标题树 + 面包屑 + 无标记标题识别 + 边界。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.assemble import assemble, detect_heading  # noqa: E402
from core.chunk import chunk_blocks  # noqa: E402


class TestDetectHeading(unittest.TestCase):
    def test_hash_mark(self):
        self.assertEqual(detect_heading("# 标题"), (1, "标题"))
        self.assertEqual(detect_heading("## 二级"), (2, "二级"))
        self.assertEqual(detect_heading("### 三级"), (3, "三级"))

    def test_no_mark_ordinal(self):
        self.assertEqual(detect_heading("第一章 绪论")[1], "第一章 绪论")
        self.assertEqual(detect_heading("第1讲 变量")[1], "第1讲 变量")

    def test_no_mark_whitelist(self):
        for w in ("小结", "重点", "练习", "参考资料"):
            self.assertIsNotNone(detect_heading(w), f"{w} 应识别为标题")

    def test_not_heading(self):
        for line in ("普通正文句子", "这是一段很长很长很长很长很长很长很长很长很长很长很长的正文超过三十字",
                     "2026 年", "3.14 是圆周率", "Python 3.12", ""):
            self.assertIsNone(detect_heading(line), f"{line!r} 不应识别为标题")

    def test_long_line_not_heading(self):
        # 实际字符数 > _MAX_NOMARK_LEN(30) 才不被当标题
        self.assertIsNone(detect_heading("第1讲 这是一个超过三十个字符的超长标题测试用例示例内容补充再多一点字"))


class TestAssemble(unittest.TestCase):
    def test_breadcrumb(self):
        md = "# 根\n\n## 子\n\n正文内容。\n\n### 孙\n\n再内容。\n"
        blocks = assemble(md)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0].breadcrumb, ["根"])
        self.assertEqual(blocks[1].breadcrumb, ["根", "子"])
        self.assertEqual(blocks[2].breadcrumb, ["根", "子", "孙"])

    def test_body_assignment(self):
        md = "# 根\n\n## 子\n\n正文A。\n\n正文B。\n"
        blocks = assemble(md)
        # 空行作为段落边界保留（A2 段落切依赖）→ 块内段落用空行分隔
        self.assertEqual(blocks[1].text, "正文A。\n\n正文B。")

    def test_leading_body_root(self):
        md = "开头正文。\n\n# 根\n\n内容。\n"
        blocks = assemble(md)
        self.assertEqual(blocks[0].title, "")
        self.assertIn("开头正文", blocks[0].text)

    def test_empty(self):
        self.assertEqual(assemble(""), [])
        self.assertEqual(assemble("   \n\n  "), [])

    # ── A3 定位（Task-04/05）：无标题不建假树 ──

    def test_no_heading_single_root(self):
        """无标题多段正文 → 1 个根块（不建假树、不崩）。"""
        blocks = assemble("第一段。\n\n第二段。\n\n第三段。\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].title, "")

    def test_no_heading_with_codeblock(self):
        """含代码块的无标题 → 1 根块，代码块并入正文。"""
        blocks = assemble("开头。\n\n```python\nx = 1\n```\n\n结尾。\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].title, "")

    def test_no_heading_with_frontmatter(self):
        """含 frontmatter 的无标题 → 1 根块（frontmatter 跳过）。"""
        blocks = assemble("---\ntitle: x\n---\n正文甲。\n\n正文乙。\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].title, "")

    def test_no_heading_splittable(self):
        """无标题根块可被 A2 段落切消费（联动下游 chunk）。"""
        md = "段落甲。内容。" * 40 + "\n\n" + "段落乙。内容。" * 40
        blocks = assemble(md)
        chunks = chunk_blocks(blocks, max_chars=400)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertTrue(c["text"].rstrip().endswith("。"))

    def test_heading_tree_regression(self):
        """有标题 md：正常建树（回归，A3 不破坏）。"""
        md = "# 根\n\n## 子\n\n正文。\n\n### 孙\n\n内容。\n"
        blocks = assemble(md)
        self.assertEqual([b.title for b in blocks], ["根", "子", "孙"])
        self.assertEqual(blocks[2].breadcrumb, ["根", "子", "孙"])


if __name__ == "__main__":
    unittest.main()
