# -*- coding: utf-8 -*-
"""core/concepts + services/orchestrator.build_concepts 测试（D7 概念页）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.core.concepts import build_concept_page, extract_terms, find_context  # noqa: E402
from md_rewrite_engine.services.orchestrator import build_concepts  # noqa: E402


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestConcepts(unittest.TestCase):
    def test_extract_terms_dedup(self):
        t = "**Hidden Markov Model** 甲。\n**Baum-Welch** 乙。\n**Hidden Markov Model** 丙。\n"
        self.assertEqual(extract_terms(t), ["Hidden Markov Model", "Baum-Welch"])

    def test_extract_empty(self):
        self.assertEqual(extract_terms("无粗体"), [])
        self.assertEqual(extract_terms(None), [])

    def test_find_context(self):
        ctx = find_context("定义：Hidden Markov Model 是概率模型。\n", "Hidden Markov Model")
        self.assertEqual(ctx, ["定义：Hidden Markov Model 是概率模型。"])

    def test_build_page(self):
        pg = build_concept_page("HMM", [{"file": "01.md", "contexts": ["HMM 定义"]}])
        self.assertIn("type: concept", pg)
        self.assertIn("# HMM", pg)
        self.assertIn("[[01.md]]", pg)

    def test_build_concepts_integration(self):
        td = tempfile.mkdtemp()
        _write(os.path.join(td, "01_a.md"),
               "# A\n**Hidden Markov Model** 是概率模型。\n**Baum-Welch** 估计。\n")
        _write(os.path.join(td, "02_b.md"), "# B\n**Hidden Markov Model** 语音识别。\n")
        r = build_concepts(td)
        self.assertTrue(r["ok"])
        self.assertEqual(r["concepts"], 2)
        pg_path = os.path.join(td, "concepts", "hidden_markov_model.md")
        self.assertTrue(os.path.isfile(pg_path))
        text = open(pg_path, encoding="utf-8").read()
        self.assertIn("[[01_a.md]]", text)
        self.assertIn("[[02_b.md]]", text)
        self.assertIn("是概率模型", text)

    def test_build_concepts_dir_missing(self):
        r = build_concepts(os.path.join(tempfile.mkdtemp(), "no"))
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
