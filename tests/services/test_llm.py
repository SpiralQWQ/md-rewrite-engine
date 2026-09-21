# -*- coding: utf-8 -*-
"""services/llm 单元测试：JSON 容错 / prompt 组装 / 三环节调用。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.services import llm  # noqa: E402


class TestLlm(unittest.TestCase):
    def test_extract_json_clean(self):
        self.assertEqual(llm._extract_json('{"a": 1}'), {"a": 1})

    def test_extract_json_wrapped(self):
        self.assertEqual(llm._extract_json('好的{"a": 1}完成'), {"a": 1})

    def test_extract_json_newline(self):
        obj = llm._extract_json('{"rewritten": "# 标题\n第一行\n第二行", "s": "要点"}')
        self.assertEqual(obj.get("rewritten"), "# 标题\n第一行\n第二行")

    def test_extract_json_fallback(self):
        out = llm._extract_json("score: 85 分")
        self.assertIn("score", out)

    def test_extract_json_empty(self):
        self.assertEqual(llm._extract_json(""), {})

    def test_build_rewrite_prompt_inject(self):
        spec = {"frontmatter": ["title"], "structure": ["summary"], "style_rules": ["通俗"]}
        sysp, usrp = llm.build_rewrite_prompt("内容", "前摘要", "术语表", spec, hint="修正X")
        self.assertIn("frontmatter", sysp)
        self.assertIn("前文摘要", usrp)
        self.assertIn("术语表", usrp)
        self.assertIn("修正X", usrp)

    def test_rewrite_prompt_accuracy_and_ai_infer(self):
        """示例·准确（教学留白，不强标出处）+ AI推断标注 进 rewrite system。"""
        sysp, _ = llm.build_rewrite_prompt("内容", "摘要")
        self.assertIn("示例·准确", sysp)
        self.assertIn("AI推断标注", sysp)
        self.assertIn("[AI推断]", sysp)

    def test_rewrite_prompt_b4(self):
        """B4 低置信标注 进 rewrite system。"""
        sysp, _ = llm.build_rewrite_prompt("内容", "摘要")
        self.assertIn("低置信标注", sysp)
        self.assertIn("[低置信]", sysp)

    def test_run_rewrite(self):
        def fake(user, system="", model_key="rewrite"):
            return '{"rewritten": "重排后\\n含换行", "summary": "要点", "merge_with_next": true}'
        r = llm.run_rewrite("原文", "前", _call=fake)
        self.assertEqual(r[0], "重排后\n含换行")
        self.assertEqual(r[1], "要点")
        self.assertTrue(r[2])

    def test_run_rewrite_no_json_fallback(self):
        r = llm.run_rewrite("原文x", "", _call=lambda *a, **k: "纯文本")
        self.assertEqual(r[0], "原文x")
        self.assertFalse(r[2])

    def test_run_quality(self):
        q = llm.run_quality("原", "重", _call=lambda *a, **k: '{"issues": ["遗漏X", "矛盾"]}')
        self.assertEqual(q, ["遗漏X", "矛盾"])

    def test_run_scoring(self):
        sc = llm.run_scoring("x", _call=lambda *a, **k: '{"score": 88}')
        self.assertEqual(sc, 88.0)
        self.assertEqual(llm.run_scoring("x", _call=lambda *a, **k: "乱"), 0.0)

    def test_quality_prompt_kb_orientation(self):
        """P4 质检适配知识库+留白：知识完整/事实准确/教学线索/结构可定位。"""
        sysp, _ = llm.build_quality_prompt("原", "重")
        for kw in ("教学知识库", "知识完整", "教学线索", "结构可定位"):
            self.assertIn(kw, sysp)
        self.assertNotIn("写得深", sysp)  # 不再比详细度

    def test_scoring_prompt_kb_orientation(self):
        """P5 评分适配知识库+留白：90+/70-89/<70 档位，非 95 详细度。"""
        sysp, _ = llm.build_scoring_prompt("笔记")
        for kw in ("教学知识库", "90+", "70-89"):
            self.assertIn(kw, sysp)
        self.assertNotIn("偏浅需补详细度", sysp)


if __name__ == "__main__":
    unittest.main()
