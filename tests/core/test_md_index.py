# -*- coding: utf-8 -*-
"""core/md_index 单元测试：frontmatter 解析 / 摘要提取 / BOM 鲁棒 / 索引渲染。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))

from md_rewrite_engine.core.md_index import (  # noqa: E402
    parse_frontmatter, _skip_frontmatter, first_heading, summary_line, build_index,
)


class TestFrontmatter(unittest.TestCase):
    def test_normal(self):
        fm = parse_frontmatter("---\ntitle: 测试\nstatus: final\n---\n\n正文")
        self.assertEqual(fm, {"title": "测试", "status": "final"})

    def test_tags_list(self):
        fm = parse_frontmatter("---\ntags: [PDF, Scrapy, 教程]\n---\n")
        self.assertEqual(fm["tags"], ["PDF", "Scrapy", "教程"])

    def test_no_frontmatter(self):
        self.assertEqual(parse_frontmatter("没有 frontmatter 的正文"), {})
        self.assertEqual(parse_frontmatter(""), {})

    def test_bom(self):
        # 写盘带 BOM：首行 `﻿---` 曾致解析失败返回 {}
        text = "﻿---\ntitle: BOM笔记\nstatus: final\n---\n\n正文"
        fm = parse_frontmatter(text)
        self.assertEqual(fm["title"], "BOM笔记")
        self.assertEqual(fm["status"], "final")


class TestSkipFrontmatter(unittest.TestCase):
    def test_normal(self):
        body = _skip_frontmatter("---\ntitle: x\n---\n\n# 标题\n正文")
        self.assertIn("# 标题", body)
        self.assertNotIn("title", body)

    def test_bom(self):
        # BOM 下 frontmatter 曾被原样保留（title 混入正文/摘要）
        body = _skip_frontmatter("﻿---\ntitle: x\n---\n\n# 标题\n正文")
        self.assertNotIn("title:", body)
        self.assertIn("# 标题", body)

    def test_no_frontmatter_passthrough(self):
        self.assertEqual(_skip_frontmatter("直接正文"), "直接正文")


class TestSummaryHeading(unittest.TestCase):
    def test_summary_skips_quote_and_heading(self):
        text = "# 标题\n\n> 一句话总结：**内容 A**\n\n- **定义**：内容 B\n"
        # summary_line 取第一个非空非标题行（引用行也算内容行，逐字符截 60）
        s = summary_line(text)
        self.assertTrue(s.startswith(">"))

    def test_summary_skips_toc_link(self):
        # 篇内目录的链接行不是摘要 → 跳过取下一行
        text = "# 标题\n\n- [第一节](#第一节)\n- [第二节](#第二节)\n\n真正的摘要行\n"
        self.assertEqual(summary_line(text), "真正的摘要行")

    def test_first_heading_after_fm(self):
        self.assertEqual(first_heading("---\ntitle: x\n---\n\n# 真标题\n"), "真标题")


class TestBuildIndex(unittest.TestCase):
    def test_basic(self):
        notes = [
            {"file": "01.md", "title": "第一讲", "summary": "摘要一"},
            {"file": "02.md", "title": "第二讲", "summary": "摘要二"},
        ]
        idx = build_index("测试课程", notes)
        self.assertIn("course: 测试课程", idx)
        self.assertIn("notes: 2", idx)
        self.assertIn("[[01.md|第一讲]]", idx)
        self.assertIn("摘要一", idx)

    def test_empty_notes(self):
        idx = build_index("空课程", [])
        self.assertIn("notes: 0", idx)


if __name__ == "__main__":
    unittest.main()
