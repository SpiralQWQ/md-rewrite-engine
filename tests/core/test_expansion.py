# -*- coding: utf-8 -*-
"""core/verify 单元测试：丰富度判定（膨胀率 + 聚合豁免，Task-01 v0.4.5）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))

from md_rewrite_engine.core.verify import (  # noqa: E402
    expansion_ratio, expansion_verdict, _content_len, _structured_carry,
    _kp_cover, _src_sections, _unit_ratios,
)


class TestContentLen(unittest.TestCase):
    def test_strips_frontmatter(self):
        t = "---\ntitle: x\n---\n\n正文内容在这里"
        self.assertEqual(_content_len(t), len("正文内容在这里"))

    def test_strips_md_marks_and_ws(self):
        t = "# 标题\n\n- **加粗**：内容\n"
        # 剥 #、-、*、`、|、>、[]() 与空白后 = "标题加粗：内容"
        self.assertEqual(_content_len(t), len("标题加粗：内容"))

    def test_empty(self):
        self.assertEqual(_content_len(""), 0)
        self.assertEqual(_content_len(None), 0)


class TestExpansionRatio(unittest.TestCase):
    def test_equal(self):
        self.assertAlmostEqual(expansion_ratio("内容 ABC", "内容 ABC"), 1.0)

    def test_expansion(self):
        self.assertGreater(expansion_ratio("短。", "扩写后的长笔记，比源多了很多很多内容。"), 1.0)

    def test_compression(self):
        self.assertLess(expansion_ratio("很长的源。" * 20, "短笔记"), 1.0)

    def test_empty_src(self):
        self.assertEqual(expansion_ratio("", "x"), 0.0)
        self.assertEqual(expansion_ratio(None, "x"), 0.0)

    def test_empty_note(self):
        self.assertEqual(expansion_ratio("源", ""), 0.0)


class TestStructuredCarry(unittest.TestCase):
    def test_table_and_code_counted(self):
        note = "```python\nx = 1\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        self.assertGreater(_structured_carry(note), 0)

    def test_plain_prose_not_counted(self):
        self.assertEqual(_structured_carry("纯正文没有结构化载体"), 0)

    def test_none(self):
        self.assertEqual(_structured_carry(None), 0)


class TestKpCover(unittest.TestCase):
    def test_counts_h2_h3(self):
        note = "## A\n\n### B\n\n### C\n"
        self.assertEqual(_kp_cover(note), 3)

    def test_none(self):
        self.assertEqual(_kp_cover(None), 0)


class TestSrcSections(unittest.TestCase):
    def test_numbered_h2(self):
        src = "## 3.1 选择器\n\n## 3.2 XPath\n"
        self.assertEqual(_src_sections(src), 2)

    def test_cjk_punct(self):
        # 题库体：'## 1，题目'（编号后全角逗号）
        src = "## 1，题A\n\n## 3, 题B\n"
        self.assertEqual(_src_sections(src), 2)

    def test_fallback_all_h2(self):
        src = "## 无编号标题A\n\n## 无编号标题B\n"
        self.assertEqual(_src_sections(src), 2)


class TestUnitRatios(unittest.TestCase):
    def test_paired_units(self):
        src = "## 1，题A\n" + "内容" * 50 + "\n\n## 2，题B\n" + "内容" * 50
        note = "### 1 · 题A\n答案\n\n### 2 · 题B\n答案\n"
        r = _unit_ratios(src, note)
        self.assertEqual(len(r), 2)
        self.assertTrue(all(x < 1 for x in r))

    def test_note_zhishi_prefix(self):
        # 题库详解体：笔记标题「### 知识点 N ·」也要配对（漏认则逐单元静默跳过）
        src = "## 1，题A\n" + "内容" * 50 + "\n\n## 2，题B\n" + "内容" * 50
        note = "### 知识点 1 · 题A\n答案\n\n### 知识点 2 · 题B\n答案\n"
        r = _unit_ratios(src, note)
        self.assertEqual(len(r), 2)

    def test_none_src(self):
        self.assertEqual(_unit_ratios(None, "note"), [])


class TestExpansionVerdict(unittest.TestCase):
    """豁免检测方案 v6 三区间制（红线30% / 豁免区30~80% / 直过≥80%）。"""

    def test_pass_direct(self):
        src = "源内容" * 100
        note = "笔记内容" * 95          # 膨胀率 ~0.95 ≥ 0.80
        v = expansion_verdict(src, note)
        self.assertTrue(v["ok"])
        self.assertFalse(v["exempt"])

    def test_fail_below_redline(self):
        src = "源内容" * 100
        note = "薄" * 10                 # 膨胀率极低 < 30%
        v = expansion_verdict(src, note)
        self.assertFalse(v["ok"])
        self.assertIn("绝对红线", v["reason"])

    def test_exempt_aggregation(self):
        # 合理聚合：低膨胀率 + 知识点覆盖 + 结构化承载 + 逐单元达标
        src = ("## 1，题A\n" + "详细内容" * 80 + "\n\n## 2，题B\n" + "详细内容" * 80)
        note = ("### 1 · 题A\n\n```python\ncode_example = 1\n" + "x" * 200 + "\n```\n\n"
                "### 2 · 题B\n\n| a | b |\n|---|---|\n" + "| 1 | 2 |\n" * 60)
        v = expansion_verdict(src, note)
        self.assertTrue(v["ok"], v["reason"])
        self.assertTrue(v["exempt"])

    def test_fail_compression_in_exempt_zone(self):
        # 豁免区但逐单元被压缩（无结构化承载）→ FAIL
        src = "## 1，题A\n" + "详细推导过程" * 100 + "\n\n## 2，题B\n" + "详细推导" * 100
        note = "### 1 · 题A\n一行结论。\n\n### 2 · 题B\n另一行结论。\n"
        v = expansion_verdict(src, note)
        self.assertFalse(v["ok"], v["reason"])

    def test_dedup_threshold(self):
        # 去重场景：dedup 阈值 0.65 直过 vs general 0.80 豁免区。
        # 膨胀率 0.735 落在 [0.65, 0.80) 区间：gen 触发豁免、dedup 直过
        src = "## 1，题A\n" + "内容" * 100
        note = ("### 1 · 题A\n" + "内容" * 62 + "\n\n```python\ncode = 1\n" + "x" * 10 + "\n```")
        v_gen = expansion_verdict(src, note)         # general 0.80：豁免区
        v_dedup = expansion_verdict(src, note, dedup=True)  # dedup 0.65：直过
        self.assertTrue(v_gen["exempt"], v_gen["reason"])
        self.assertFalse(v_dedup["exempt"])
        self.assertTrue(v_dedup["ok"])

    def test_none_inputs(self):
        self.assertFalse(expansion_verdict(None, None)["ok"])
        self.assertFalse(expansion_verdict("", "")["ok"])

    def test_schema_keys(self):
        src = "源内容" * 100
        v = expansion_verdict(src, "笔记内容" * 100)
        for k in ("ratio", "threshold", "carry", "kp_note", "kp_src",
                  "kp_cover", "unit_median", "ok", "exempt", "reason"):
            self.assertIn(k, v)


if __name__ == "__main__":
    unittest.main()
