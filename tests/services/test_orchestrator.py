# -*- coding: utf-8 -*-
"""services/orchestrator 集成测试：全链路 / 防呆 / 打回重写。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.services.orchestrator import process  # noqa: E402


def _make_fake(flaky_quality=False):
    """mock LLM。flaky_quality=True 时首次质检报错，之后通过。"""
    state = {"rewrite": 0, "quality_check": 0, "scoring": 0}

    def fake(user, system="", model_key="rewrite"):
        state[model_key] += 1
        if model_key == "rewrite":
            return json.dumps({"rewritten": f"# 重排结果\n{user[-80:]}",
                               "summary": "要点", "merge_with_next": False})
        if model_key == "quality_check":
            if flaky_quality and state["quality_check"] == 1:
                return json.dumps({"issues": ["遗漏概念X"]})
            return json.dumps({"issues": []})
        return json.dumps({"score": 90})

    return fake, state


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._src = os.path.join(self._td, "in.md")
        with open(self._src, "w", encoding="utf-8") as f:
            f.write("# 测试文档\n\n## 第一节\n\n变量与函数。\n\n## 第二节\n\n循环while与for。\n")

    def test_full_pipeline_write(self):
        out = os.path.join(self._td, "out.md")
        fake, st = _make_fake()
        r = process(self._src, output_path=out, _call=fake)
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(r["units"], 1)
        self.assertIn("# 重排结果", r["output"])
        self.assertTrue(os.path.isfile(out))
        self.assertGreaterEqual(st["rewrite"], 1)
        self.assertGreaterEqual(st["quality_check"], 1)

    def test_file_missing(self):
        fake, _ = _make_fake()
        r = process(os.path.join(self._td, "no.md"), _call=fake)
        self.assertFalse(r["ok"])
        self.assertIn("文件不存在", r["error"])

    def test_empty_content(self):
        empty = os.path.join(self._td, "empty.md")
        with open(empty, "w", encoding="utf-8") as f:
            f.write("   \n\n  ")
        fake, _ = _make_fake()
        r = process(empty, _call=fake)
        self.assertFalse(r["ok"])

    def test_retry_then_pass(self):
        fake, st = _make_fake(flaky_quality=True)
        r = process(self._src, max_rewrite_retries=1, _call=fake)
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(st["rewrite"], 2)

    def test_no_output_path(self):
        fake, _ = _make_fake()
        r = process(self._src, _call=fake)
        self.assertEqual(r["output_path"], "")
        self.assertGreater(len(r["output"]), 0)

    def test_inferred_count(self):
        """D5：process 返回 [AI推断] 计数。"""
        def fake(user, system="", model_key="rewrite"):
            if model_key == "rewrite":
                return json.dumps({"rewritten": "正文 [AI推断] 补充。\n[AI推断] 再补。",
                                   "summary": "要点", "merge_with_next": False})
            if model_key == "quality_check":
                return json.dumps({"issues": []})
            return json.dumps({"score": 90})
        r = process(self._src, _call=fake)
        self.assertEqual(r["inferred"], 2)

    def test_state_resume_skip_llm(self):
        """B3：断点命中 → 返回缓存输出，LLM 不重调，输出与一次跑完一致。"""
        st = os.path.join(self._td, "st.json")
        fake, state = _make_fake()
        r1 = process(self._src, state_path=st, _call=fake)
        self.assertTrue(r1["ok"])
        calls1 = sum(state.values())
        r2 = process(self._src, state_path=st, _call=fake)
        self.assertTrue(r2["resumed"])
        self.assertEqual(sum(state.values()), calls1)  # LLM 不重调
        self.assertEqual(r2["output"], r1["output"])

    def test_state_corrupt_no_break(self):
        """B3：损坏状态文件 → 不崩、从头跑。"""
        st = os.path.join(self._td, "st.json")
        with open(st, "w", encoding="utf-8") as f:
            f.write("损坏{")
        fake, _ = _make_fake()
        r = process(self._src, state_path=st, _call=fake)
        self.assertTrue(r["ok"])
        self.assertFalse(r["resumed"])

    def test_no_state_disabled(self):
        """B3：无 state_path → 不启用断点。"""
        fake, _ = _make_fake()
        r = process(self._src, _call=fake)
        self.assertFalse(r.get("resumed", False))

    def test_low_conf_count(self):
        """B4：process 返回 [低置信] 计数。"""
        def fake(user, system="", model_key="rewrite"):
            if model_key == "rewrite":
                return json.dumps({"rewritten": f"正文 [低置信] 存疑处。\n{user[-60:]}",
                                   "summary": "要点", "merge_with_next": False})
            if model_key == "quality_check":
                return json.dumps({"issues": []})
            return json.dumps({"score": 90})
        r = process(self._src, _call=fake)
        self.assertEqual(r["low_conf"], 1)


if __name__ == "__main__":
    unittest.main()
