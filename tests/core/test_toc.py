# -*- coding: utf-8 -*-
"""core/toc 单元测试：篇内目录生成（提取/幂等/主标题排除/边界）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.toc import build_toc, extract_headings, render_toc  # noqa: E402


class TestToc(unittest.TestCase):
    SAMPLE = (
        "# 主标题\n"
        "## 第一节\n"
        "正文内容。\n"
        "### 知识点 A\n"
        "### 知识点 B\n"
        "## 第二节\n"
        "### 知识点 C\n"
    )

    def test_extract_headings_levels(self):
        hs = extract_headings(self.SAMPLE)
        self.assertEqual(hs, [(1, "主标题"), (2, "第一节"), (3, "知识点 A"),
                               (3, "知识点 B"), (2, "第二节"), (3, "知识点 C")])

    def test_build_skips_main_title(self):
        # 文档主标题（第一个 H1）不列入 TOC
        new, hs = build_toc(self.SAMPLE)
        self.assertNotIn("主标题", new.split("## 📑 本篇目录")[1].splitlines()[1] if "本篇目录" in new else "")
        self.assertEqual(hs[0], (2, "第一节"))

    def test_build_inserts_after_main_title(self):
        new, hs = build_toc(self.SAMPLE)
        self.assertIn("## 📑 本篇目录", new)
        # TOC 在主标题之后、第一节之前
        pos_title = new.index("# 主标题")
        pos_toc = new.index("本篇目录")
        pos_sec = new.index("## 第一节")
        self.assertTrue(pos_title < pos_toc < pos_sec)

    def test_build_toc_has_links(self):
        new, _ = build_toc(self.SAMPLE)
        self.assertIn("- [第一节](#第一节)", new)
        self.assertIn("- [知识点 A](#知识点-a)", new)

    def test_build_idempotent(self):
        once, _ = build_toc(self.SAMPLE)
        twice, _ = build_toc(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count("本篇目录"), 1)

    def test_build_frontmatter_insert_after_fm(self):
        md = "---\ntitle: 测试\n---\n\n# 主\n## 内容\n"
        new, _ = build_toc(md)
        # frontmatter 闭合 --- 后是主标题，TOC 在两者之后
        self.assertIn("---\n\n# 主\n## 📑 本篇目录", new)

    def test_build_empty_input(self):
        self.assertEqual(build_toc(""), ("", []))
        self.assertEqual(build_toc(None), (None, []))
        self.assertEqual(build_toc("   \n "), ("   \n ", []))

    def test_build_no_headings(self):
        new, hs = build_toc("纯正文，没有标题。\n\n再来一行。")
        self.assertEqual(hs, [])
        self.assertEqual(new, "纯正文，没有标题。\n\n再来一行。")

    def test_extract_skip_codeblock(self):
        md = "# 主\n\n```\n# 代码块里的标题不算\n```\n\n## 真标题\n"
        hs = extract_headings(md)
        self.assertEqual(hs, [(1, "主"), (2, "真标题")])

    def test_render_no_headings_empty(self):
        self.assertEqual(render_toc([]), "")

    def test_build_replaces_existing_toc(self):
        # 已有 TOC 的笔记：重新生成不产生两个 TOC
        first, _ = build_toc(self.SAMPLE)
        second, hs = build_toc(first)
        self.assertEqual(second.count("本篇目录"), 1)
        self.assertTrue(hs)


if __name__ == "__main__":
    unittest.main()
