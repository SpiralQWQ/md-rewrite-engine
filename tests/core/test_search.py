# -*- coding: utf-8 -*-
"""core/search + services/orchestrator.search_course 测试（D8 词法检索）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.search import search, split_query  # noqa: E402
from services.orchestrator import search_course  # noqa: E402


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestSearch(unittest.TestCase):
    def test_split_dedup(self):
        self.assertEqual(split_query("隐 Markov,隐 Markov"), ["隐", "markov"])

    def test_split_empty(self):
        self.assertEqual(split_query(""), [])
        self.assertEqual(split_query(None), [])

    def test_search_hit(self):
        r = search({"a.md": "# 第1讲\n隐马尔可夫模型。\n"}, "隐马尔可夫")
        self.assertEqual(r[0]["file"], "a.md")
        self.assertIn("隐马尔可夫", r[0]["hits"][0])

    def test_search_no_match(self):
        self.assertEqual(search({"a.md": "正文"}, "不存在词"), [])

    def test_search_empty_inputs(self):
        self.assertEqual(search({}, "x"), [])
        self.assertEqual(search(None, "x"), [])

    def test_search_course_integration(self):
        td = tempfile.mkdtemp()
        _write(os.path.join(td, "01_a.md"), "# A\n**Hidden Markov Model** 概率模型。\n")
        _write(os.path.join(td, "02_b.md"), "# B\n维特比。\n")
        r = search_course(td, "Hidden Markov")
        self.assertTrue(r["ok"])
        self.assertEqual(r["results"][0]["file"], "01_a.md")

    def test_search_course_no_match(self):
        r = search_course(tempfile.mkdtemp(), "不存在词")
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
