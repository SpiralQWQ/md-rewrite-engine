# -*- coding: utf-8 -*-
"""core/verify 单元测试：对账检出缺失 / 评分 / 组合 check。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.core.verify import (check, extract_keypoints, extract_links, find_missing_source,  # noqa: E402
                         reconcile, score, term_variants, validate_confidence,
                         validate_frontmatter_schema, validate_links, validate_relations)


class TestVerify(unittest.TestCase):
    ORIG = "Python是解释型语言，支持变量、函数、类。使用len()获取长度。循环for与while。版本3.12发布。"

    def test_reconcile_complete(self):
        r = reconcile(self.ORIG, self.ORIG + "补充。")
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])

    def test_reconcile_missing(self):
        r = reconcile(self.ORIG, "Python是解释型语言。")
        self.assertFalse(r["ok"])
        self.assertGreater(len(r["missing"]), 0)

    def test_score_empty(self):
        self.assertEqual(score("")["score"], 0)
        self.assertEqual(score("   ")["score"], 0)

    def test_score_structure(self):
        s = score("# 笔记\n\n完整内容若干行。\n\n" + "内容" * 20)
        self.assertGreaterEqual(s["score"], 60)

    def test_check_pass(self):
        c = check(self.ORIG, self.ORIG + "\n# 补充")
        self.assertTrue(c["pass"])

    def test_check_missing(self):
        c = check(self.ORIG, "只有一句话。")
        self.assertFalse(c["pass"])
        self.assertIn("缺失", c["issues"][0])

    def test_check_empty_output(self):
        self.assertFalse(check(self.ORIG, "")["pass"])

    # ── Task-01 新语义：机械对账 = 数字硬 + 英文软 + 中文交 AI ──
    def test_extract_no_chinese(self):
        kp = extract_keypoints("这里是一下 3000 其实 Python 说明")
        self.assertNotIn("这里", kp)
        self.assertNotIn("一下", kp)
        self.assertNotIn("其实", kp)
        self.assertIn("python", kp)
        self.assertIn("3000", kp)

    def test_extract_digit_min2(self):
        self.assertNotIn("0", extract_keypoints("端口 0"))
        self.assertNotIn("3", extract_keypoints("版本 3"))
        self.assertIn("3.12", extract_keypoints("版本 3.12"))
        self.assertIn("300", extract_keypoints("端口 300"))

    def test_reconcile_digit_merge(self):
        # ASR 拆散 300 0 → 重排 3000，算覆盖（合并匹配）
        r = reconcile("端口 300 0", "端口 3000")
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])

    def test_reconcile_en_soft_warning(self):
        # 英文缺失（ASR 错听被纠正）→ warnings 软提示，不判不通过
        r = reconcile("Powers hell 与 3000", "PowerShell 与 3000")
        self.assertTrue(r["ok"])
        self.assertIn("powers", r["warnings"])

    def test_reconcile_no_digit_ok(self):
        r = reconcile("只有中文概念没有数字", "中文概念重排后")
        self.assertTrue(r["ok"])
        self.assertEqual(r["total"], 0)

    def test_reconcile_digit_missing_fail(self):
        r = reconcile("端口 3000 与 6379", "端口 3000")
        self.assertFalse(r["ok"])
        self.assertIn("6379", r["missing"])

    def test_extract_skip_long_id(self):
        # 超长纯数字（视频ID/哈希）非教学内容，跳过防机械对账误报
        kp = extract_keypoints("视频ID 7657102214691634809 端口 3000")
        self.assertNotIn("7657102214691634809", kp)
        self.assertIn("3000", kp)

    def test_check_warnings_field(self):
        c = check("abc 3000", "重排后 3000 无 abc")
        self.assertIn("warnings", c)
        self.assertIsInstance(c["warnings"], list)


class TestLinks(unittest.TestCase):
    """D2 链接校验（Task-12）：extract_links / validate_links。"""

    def test_extract_forms(self):
        t = "前置 [[01_第1讲.md#变量|变量]]，后继 [[02_第2讲.md]]，相关 [[03_第3讲.md|循环]]"
        self.assertEqual(extract_links(t), ["01_第1讲.md", "02_第2讲.md", "03_第3讲.md"])

    def test_extract_empty(self):
        self.assertEqual(extract_links(""), [])
        self.assertEqual(extract_links(None), [])
        self.assertEqual(extract_links("无链接文本"), [])

    def test_validate_broken(self):
        r = validate_links("[[a.md]] [[b.md]]", {"a.md"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["broken"], ["b.md"])
        self.assertEqual(r["links"], 2)

    def test_validate_all_ok(self):
        r = validate_links("[[a.md]] [[b.md]]", {"a.md", "b.md"})
        self.assertTrue(r["ok"])

    def test_validate_no_known_skip(self):
        self.assertTrue(validate_links("[[a.md]]")["ok"])

    def test_validate_none_input(self):
        self.assertTrue(validate_links(None)["ok"])


class TestRelations(unittest.TestCase):
    """D3 关联字段校验（Task-16）：validate_relations。"""

    KNOWN = {"01_第1讲.md", "01_第1讲", "02_第2讲.md", "02_第2讲"}

    def test_all_valid(self):
        r = validate_relations({"prerequisites": "01_第1讲.md#变量", "next": "02_第2讲.md",
                                "related": "01_第1讲.md"},
                               self.KNOWN)
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])

    def test_missing_field(self):
        r = validate_relations({"prerequisites": "01_第1讲.md"}, self.KNOWN)
        self.assertIn("next", r["missing"])
        self.assertIn("related", r["missing"])

    def test_empty_value_missing(self):
        r = validate_relations({"prerequisites": "  ", "next": "02_第2讲.md"}, self.KNOWN)
        self.assertIn("prerequisites", r["missing"])

    def test_broken_target(self):
        r = validate_relations({"prerequisites": "99_不存在.md"}, self.KNOWN)
        self.assertFalse(r["ok"])
        self.assertEqual(r["broken"], ["prerequisites=99_不存在.md"])

    def test_anchor_stripped(self):
        """去 #锚点后匹配。"""
        r = validate_relations({"prerequisites": "01_第1讲.md#变量"}, self.KNOWN)
        self.assertTrue(r["ok"])

    def test_no_known_only_missing(self):
        r = validate_relations({"prerequisites": "任意"}, None)
        self.assertTrue(r["ok"])
        self.assertIn("next", r["missing"])

    def test_none_input(self):
        self.assertTrue(validate_relations(None)["ok"])
        self.assertTrue(validate_relations("x")["ok"])


class TestSource(unittest.TestCase):
    """D4 条目级引用抽查（Task-19）：find_missing_source。"""

    def test_all_sourced(self):
        t = ("**示例** 前向算法计算 (来源: 第3讲 12:34)。\n"
             "> 原句：观察概率 (来源: 第3讲 12:34)\n"
             "示例：维特比 (来源：第4讲 05:00)\n")
        self.assertEqual(find_missing_source(t), [])

    def test_missing_detected(self):
        t2 = "**示例** 无出处。\n**原句** 也无出处。\n例如：第三个示例。\n"
        self.assertEqual(len(find_missing_source(t2)), 3)

    def test_fullwidth_source_mark(self):
        t3 = "示例：xxx（来源：第1讲 00:01）\n"
        self.assertEqual(find_missing_source(t3), [])

    def test_empty_input(self):
        self.assertEqual(find_missing_source(""), [])
        self.assertEqual(find_missing_source(None), [])


class TestConfidence(unittest.TestCase):
    """D6 置信度落值校验（Task-26）：validate_confidence。"""

    def test_valid_levels(self):
        for lv in ("high", "medium", "low"):
            self.assertTrue(validate_confidence({"confidence": lv})["ok"], lv)

    def test_missing(self):
        r = validate_confidence({})
        self.assertFalse(r["ok"])
        self.assertTrue(any("缺失" in i for i in r["issues"]))
        self.assertFalse(validate_confidence({"confidence": ""})["ok"])

    def test_invalid_level(self):
        r = validate_confidence({"confidence": "sure"})
        self.assertFalse(r["ok"])
        self.assertTrue(any("非法" in i for i in r["issues"]))

    def test_verified_valid(self):
        self.assertTrue(validate_confidence({"confidence": "low",
                                             "verified": "human_reviewed"})["ok"])

    def test_verified_invalid(self):
        self.assertFalse(validate_confidence({"confidence": "high", "verified": "yes"})["ok"])

    def test_none_input(self):
        self.assertTrue(validate_confidence(None)["ok"])
        self.assertTrue(validate_confidence("x")["ok"])


class TestSchema(unittest.TestCase):
    """C3d frontmatter schema 校验（Task-47）：validate_frontmatter_schema。"""

    def test_all_ok(self):
        r = validate_frontmatter_schema({"title": "T", "type": "x"}, ["title", "type"])
        self.assertTrue(r["ok"])

    def test_missing(self):
        r = validate_frontmatter_schema({"title": "T"}, ["title", "type"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["missing"], ["type"])

    def test_empty_value(self):
        r = validate_frontmatter_schema({"title": "", "type": "x"}, ["title", "type"])
        self.assertFalse(r["ok"])

    def test_type_error(self):
        r = validate_frontmatter_schema({"title": "T", "tags": "x"}, ["title"], {"tags": list})
        self.assertFalse(r["ok"])
        self.assertEqual(r["type_errors"], ["tags 应为列表"])

    def test_none_input(self):
        self.assertFalse(validate_frontmatter_schema(None, ["title"])["ok"])


class TestTermVariants(unittest.TestCase):
    """中文术语近形变体检测（错别字机检，Task-05）。"""

    def test_typo_detected(self):
        # 经典错字：调度器→掉度器（dist=1）
        r = term_variants("Scrapy 的调度器管理请求队列", "Scrapy 的掉度器管理请求队列")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["distance"], 1)
        self.assertIn("调度器", r[0]["term"])
        self.assertIn("掉度器", r[0]["variant"])

    def test_normal_rewrite_not_flagged(self):
        # 正常同义改写（大范围重组）不误报
        r = term_variants("调度器管理请求队列", "调度器负责请求的排队与调度")
        self.assertEqual(r, [])

    def test_kept_terms_not_flagged(self):
        # 原样保留的术语不报
        r = term_variants("用调度器干活", "调度器很能干")
        self.assertEqual(r, [])

    def test_empty_and_none(self):
        self.assertEqual(term_variants("", "x"), [])
        self.assertEqual(term_variants("x", ""), [])
        self.assertEqual(term_variants(None, None), [])

    def test_english_only(self):
        self.assertEqual(term_variants("scrapy spider selector", "scrapy spider selector"), [])

    def test_unrelated_not_flagged(self):
        # 完全不同的两段中文（距离比 >0.3）不报
        r = term_variants("苹果香蕉橘子同时出现", "猫狗兔子一起出现")
        self.assertEqual(r, [])

    def test_two_typos(self):
        r = term_variants("调度器和下载器协同工作", "掉度器和下载器协同工作")
        self.assertEqual(len(r), 1)

    def test_two_char_words_not_flagged(self):
        # 2 字段等长替换不报（常用词互转太泛：通常→通过、首先→要先，实测全是改写）
        # 构造：两侧各只含 2 字中文词（英文标点隔离，无 ≥3 字段）
        r = term_variants("通常 abc 在第 xyz 首先", "通过 abc 在第 xyz 首先")
        self.assertEqual(r, [])

    def test_virtual_word_insertion_not_flagged(self):
        # 虚词增删（不等长）放过：合法改写的主要形态
        r = term_variants("从页面中提取数据是核心", "从页面提取数据是核心")
        self.assertEqual(r, [])

    def test_cap_10(self):
        # 大量错段 → 截断 ≤10
        src = " ".join(f"术语甲{i}号描述" for i in range(15))
        dst = " ".join(f"术语乙{i}号描述" for i in range(15))
        self.assertLessEqual(len(term_variants(src, dst)), 10)


if __name__ == "__main__":
    unittest.main()
