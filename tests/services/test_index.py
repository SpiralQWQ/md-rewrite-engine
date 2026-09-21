# -*- coding: utf-8 -*-
"""services/orchestrator.build_course_index 测试：总索引生成 / 防呆 / 自扫排除 / 死链。"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.services.orchestrator import build_course_index, validate_course_links  # noqa: E402


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestCourseIndex(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp()
        _write(os.path.join(self._td, "01_第1讲.md"),
               "---\ntitle: 第1讲 变量\ntags: [nlp]\n---\n# 第1讲 变量\n> 变量与赋值。\n\n正文。\n")
        _write(os.path.join(self._td, "02_第2讲.md"),
               "---\ntitle: 第2讲 函数\n---\n# 第2讲 函数\n> 函数定义。\n\n正文。\n")
        _write(os.path.join(self._td, "03_第3讲.md"), "# 第3讲 循环\n\n循环讲解。\n")

    def test_generate_index(self):
        r = build_course_index(self._td)
        self.assertTrue(r["ok"])
        self.assertEqual(r["notes"], 3)
        idx = os.path.join(self._td, "index.md")
        self.assertTrue(os.path.isfile(idx))
        text = open(idx, encoding="utf-8").read()
        self.assertIn("okf_version: v0.2", text)
        self.assertIn("[[01_第1讲.md|第1讲 变量]]", text)
        self.assertIn("讲次总数：3", text)

    def test_links_all_valid(self):
        """死链检测：索引里 [[链接]] 指向的文件必须都存在。"""
        r = build_course_index(self._td)
        text = r["output"]
        targets = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)
        self.assertGreater(len(targets), 0)
        for t in targets:
            self.assertTrue(os.path.isfile(os.path.join(self._td, t)),
                            f"死链: {t}")

    def test_dir_missing(self):
        r = build_course_index(os.path.join(self._td, "no_such"))
        self.assertFalse(r["ok"])
        self.assertIn("不存在", r["error"])

    def test_empty_dir(self):
        r = build_course_index(tempfile.mkdtemp())
        self.assertFalse(r["ok"])
        self.assertIn("无有效笔记", r["error"])

    def test_none_dir(self):
        r = build_course_index(None)
        self.assertFalse(r["ok"])

    def test_self_scan_excluded(self):
        """index.md 不纳入统计（任意层级子目录）。"""
        r = build_course_index(self._td)
        self.assertEqual(r["notes"], 3)
        sub = os.path.join(self._td, "sub")
        os.makedirs(sub, exist_ok=True)
        r2 = build_course_index(self._td, output_path=os.path.join(sub, "index.md"))
        self.assertTrue(r2["ok"])
        r3 = build_course_index(self._td)
        self.assertEqual(r3["notes"], 3)

    def test_custom_output(self):
        out = os.path.join(self._td, "out", "my_index.md")
        r = build_course_index(self._td, output_path=out)
        self.assertTrue(r["ok"])
        self.assertTrue(os.path.isfile(out))


class TestValidateLinks(unittest.TestCase):
    """D2 悬空链接校验（Task-12）：validate_course_links。"""

    def setUp(self):
        self._td = tempfile.mkdtemp()
        _write(os.path.join(self._td, "01_第1讲.md"), "# 第1讲\n前置 [[02_第2讲.md|第2讲]]\n")
        _write(os.path.join(self._td, "02_第2讲.md"), "# 第2讲\n相关 [[01_第1讲|第1讲]] 和 [[不存在.md|悬空]]\n")
        _write(os.path.join(self._td, "03_第3讲.md"), "# 第3讲\n无链接\n")

    def test_checked_all(self):
        r = validate_course_links(self._td)
        self.assertEqual(r["checked"], 3)

    def test_broken_detected(self):
        r = validate_course_links(self._td)
        self.assertFalse(r["ok"])
        self.assertEqual(r["broken_total"], 1)
        self.assertEqual(r["broken"][0]["file"], "02_第2讲.md")
        self.assertIn("不存在.md", r["broken"][0]["links"])

    def test_no_ext_tolerance(self):
        """不带扩展 [[01_第1讲]] 不算悬空（容错）。"""
        r = validate_course_links(self._td)
        broken_all = [x for b in r["broken"] for x in b["links"]]
        self.assertNotIn("01_第1讲", broken_all)

    def test_dir_missing(self):
        r = validate_course_links(os.path.join(self._td, "no"))
        self.assertFalse(r["ok"])

    def test_empty_dir(self):
        r = validate_course_links(tempfile.mkdtemp())
        self.assertFalse(r["ok"])

    def test_relation_broken(self):
        """D3 关联字段悬空被检出并定位。"""
        _write(os.path.join(self._td, "01_第1讲.md"),
               "---\nprerequisites: 02_第2讲.md\n---\n# 第1讲\n正文\n")
        _write(os.path.join(self._td, "02_第2讲.md"),
               "---\nprerequisites: 99_不存在.md\n---\n# 第2讲\n正文\n")
        r = validate_course_links(self._td)
        self.assertFalse(r["ok"])
        self.assertEqual(r["relation_broken_total"], 1)
        self.assertTrue(any(ri["file"] == "02_第2讲.md"
                            and "prerequisites=99_不存在.md" in ri["broken"]
                            for ri in r["relation_issues"]))

    def test_citation_missing(self):
        """D4 示例缺出处被统计并定位。"""
        _write(os.path.join(self._td, "01_第1讲.md"),
               "# 第1讲\n**示例** 没出处的示例。\n**示例** 有出处 (来源: 第2讲 00:10)。\n")
        r = validate_course_links(self._td)
        self.assertEqual(r["citation_missing_total"], 1)
        self.assertEqual(r["citation_issues"][0]["file"], "01_第1讲.md")

    def test_conf_issues_and_low(self):
        """D6：confidence 缺失/非法 → conf_issues；low → 人工抽查清单。"""
        # 覆盖 setUp 的 3 篇（保持文件总数=3），只测 confidence 语义
        _write(os.path.join(self._td, "01_第1讲.md"),
               "---\nconfidence: high\nverified: human_reviewed\n---\n# 好\n正文\n")
        _write(os.path.join(self._td, "02_第2讲.md"), "---\n---\n# 缺\n正文\n")
        _write(os.path.join(self._td, "03_第3讲.md"), "---\nconfidence: low\n---\n# 低\n正文\n")
        r = validate_course_links(self._td)
        self.assertEqual(r["conf_issues_total"], 1)
        self.assertTrue(any(ci["file"] == "02_第2讲.md" for ci in r["conf_issues"]))
        self.assertEqual(r["low_conf"], ["03_第3讲.md"])

    def test_schema_issues(self):
        """C3d：frontmatter 缺必填/类型错被检出并定位。"""
        # 覆盖 setUp 的 3 篇，保持文件总数=3
        _write(os.path.join(self._td, "01_第1讲.md"),
               "---\ntitle: 好\ntype: note\ntags: [a]\n---\n# 好\n正文\n")
        _write(os.path.join(self._td, "02_第2讲.md"),
               "---\ntags: not-list\n---\n# 缺\n正文\n")
        _write(os.path.join(self._td, "03_第3讲.md"),
               "---\ntitle: 好\ntype: note\ntags: [b]\n---\n# 好\n正文\n")
        r = validate_course_links(self._td)
        self.assertEqual(r["schema_issues_total"], 1)
        self.assertEqual(r["schema_issues"][0]["file"], "02_第2讲.md")


if __name__ == "__main__":
    unittest.main()
