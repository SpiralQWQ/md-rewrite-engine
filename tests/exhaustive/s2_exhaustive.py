# -*- coding: utf-8 -*-
"""S2 穷举测试 — 路径穷举 + 边界严格 + 终点一致性（fixloop 规范）。

依据：docs/task-list-v0.3.0.md「穷举环节（S2）三层穷举」：
  executors 路由各组合 / 插槽"等本体-超时-中断" / 分块上下文 /
  打回循环边界 / 附录外置 / CLI 交互防呆。
收敛判定：high==0 && low<5 && medium<3。

全部用例 mock（注入 fake urlopen / fake call_llm），不真调 LLM、不写网络。
运行：python temp/s2_exhaustive/s2_exhaustive.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from providers import executors as EX  # noqa: E402
from providers import llm_client as lc  # noqa: E402
from core import assemble as A  # noqa: E402
from core import chunk as CH  # noqa: E402
from core import concepts as CN  # noqa: E402
from core import rewrite as RW  # noqa: E402
from core import verify as V  # noqa: E402
from services import llm as LLM  # noqa: E402
from services import orchestrator as O  # noqa: E402
from scripts import gate_check as GC  # noqa: E402
import cli  # noqa: E402

_ENV_KEYS = ("GLM_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_AUTH_TOKEN",
             "ANTHROPIC_BASE_URL", "MD_REWRITE_PROVIDER_REWRITE",
             "MD_REWRITE_PROVIDER_QUALITY_CHECK", "MD_REWRITE_PROVIDER_SCORING",
             "MD_REWRITE_PROVIDER_RECONCILE", "MD_REWRITE_MODEL_REWRITE",
             "MD_REWRITE_MODEL_QUALITY_CHECK")


def _clean_env():
    for k in _ENV_KEYS:
        os.environ.pop(k, None)


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen_factory(payload: str, seen: dict, fail_first: int = 0):
    """构造 fake urlopen：记录请求，可选前 N 次抛错。"""
    def fake(req, timeout=60):
        seen.setdefault("n", 0)
        seen["n"] += 1
        if seen["n"] <= fail_first:
            raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, None)
        body = json.loads(req.data.decode())
        seen["model"] = body.get("model")
        seen["n_msg"] = len(body.get("messages", []))
        seen["auth"] = req.headers.get("Authorization")
        return _FakeResp(payload.encode())
    return fake


class FakeLLM:
    """通用 fake call_llm：按 model_key 返回合法 JSON，重排输出保留原文关键点。"""

    def __init__(self, quality_issues=None):
        self.calls = []
        self.quality_issues = quality_issues or []

    def __call__(self, prompt, system="", model_key="rewrite", **_):
        self.calls.append(model_key)
        if model_key == "rewrite":
            return ('{"rewritten": "# 重排结果\\n\\n'
                    '这是一段测试文本，包含 123 数字。\\n\\n'
                    '包含关键信息：Alpha Beta Gamma。\\n\\n'
                    '## 概述\\n\\n本段保留全部关键信息。", '
                    '"summary": "要点", "merge_with_next": false}')
        if model_key == "quality_check":
            if self.quality_issues:
                return json.dumps({"issues": self.quality_issues.pop(0)}, ensure_ascii=False)
            return '{"issues": []}'
        if model_key == "reconcile":
            return '{"missing_concepts": []}'
        if model_key == "scoring":
            return '{"score": 95, "reason": "ok"}'
        return "{}"


def _mk_input_file(text: str) -> str:
    d = tempfile.mkdtemp(prefix="s2_in_")
    p = os.path.join(d, "in.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


_SRC = "这是一段测试文本，包含 123 数字。\n\n包含关键信息：Alpha Beta Gamma。"


# ════════════════════════════════════════════════════════════════
# 块 A · executors 路由各组合（优先级 / 非法 / 缺失回落）
# ════════════════════════════════════════════════════════════════

class TestExecutorsRouter(unittest.TestCase):
    def setUp(self):
        _clean_env()

    # ── provider 解析优先级：env > executors.provider > executors.executor > 内置 ──
    def test_provider_env_override_wins(self):
        cfg = {"rewrite": {"executor": "claude", "provider": "glm", "model": "m", "key_env": ""}}
        with patch.object(lc, "load_executors", return_value=cfg):
            os.environ["MD_REWRITE_PROVIDER_REWRITE"] = "deepseek"
            self.assertEqual(lc._provider_of("rewrite"), "deepseek")

    def test_provider_config_provider_wins(self):
        cfg = {"rewrite": {"executor": "claude", "provider": "glm", "model": "m", "key_env": ""}}
        with patch.object(lc, "load_executors", return_value=cfg):
            self.assertEqual(lc._provider_of("rewrite"), "glm")

    def test_provider_executor_maps_provider(self):
        cfg = {"rewrite": {"executor": "deepseek", "provider": "", "model": "m", "key_env": ""}}
        with patch.object(lc, "load_executors", return_value=cfg):
            self.assertEqual(lc._provider_of("rewrite"), "deepseek")

    def test_provider_claude_executor_maps_anthropic(self):
        cfg = {"rewrite": {"executor": "claude", "provider": "", "model": "m", "key_env": ""}}
        with patch.object(lc, "load_executors", return_value=cfg):
            self.assertEqual(lc._provider_of("rewrite"), "anthropic")

    def test_provider_missing_config_fallback_builtin(self):
        with patch.object(lc, "load_executors", return_value={}):
            self.assertEqual(lc._provider_of("rewrite"), "glm")
            self.assertEqual(lc._provider_of("scoring"), "glm")

    def test_provider_config_corrupt_fallback(self):
        with patch.object(lc, "load_executors", return_value=[]):  # 非 dict
            self.assertEqual(lc._provider_of("rewrite"), "glm")

    # ── model 解析优先级：env > executors.model > models.yaml > 默认 ──
    def test_model_env_override_wins(self):
        cfg = {"rewrite": {"executor": "glm", "provider": "glm", "model": "exec-model", "key_env": ""}}
        with patch.object(lc, "load_executors", return_value=cfg):
            os.environ["MD_REWRITE_MODEL_REWRITE"] = "env-model"
            self.assertEqual(lc.resolve_model("rewrite"), "env-model")

    def test_model_executors_wins_over_models_yaml(self):
        cfg = {"rewrite": {"executor": "glm", "provider": "glm", "model": "exec-model", "key_env": ""}}
        with patch.object(lc, "load_executors", return_value=cfg), \
                patch.object(lc, "load_models_config", return_value={"rewrite": "yaml-model"}):
            self.assertEqual(lc.resolve_model("rewrite"), "exec-model")

    def test_model_models_yaml_wins_over_default(self):
        with patch.object(lc, "load_executors", return_value={}), \
                patch.object(lc, "load_models_config", return_value={"rewrite": "yaml-model"}):
            self.assertEqual(lc.resolve_model("rewrite"), "yaml-model")

    def test_model_unknown_key_default(self):
        with patch.object(lc, "load_executors", return_value={}), \
                patch.object(lc, "load_models_config", return_value={}):
            self.assertEqual(lc.resolve_model("no-such-key"), "glm-4.5-air")

    def test_model_none_key_default(self):
        with patch.object(lc, "load_executors", return_value={}):
            self.assertEqual(lc.resolve_model(None), lc._DEFAULT_MODELS.get("rewrite", ""))

    # ── build_executor_entry / render / save（纯函数）──
    def test_build_entry_all_executors(self):
        for ex in EX.VALID_EXECUTORS:
            e = EX.build_executor_entry(ex)
            self.assertEqual(e["executor"], ex)
            self.assertIn("provider", e)
            self.assertIn("model", e)
            self.assertIn("key_env", e)

    def test_build_entry_invalid_empty(self):
        self.assertEqual(EX.build_executor_entry("foo"), {})
        self.assertEqual(EX.build_executor_entry(None), {})
        self.assertEqual(EX.build_executor_entry(123), {})

    def test_build_entry_overrides(self):
        e = EX.build_executor_entry("glm", model="custom", provider="deepseek", key_env="K")
        self.assertEqual(e["model"], "custom")
        self.assertEqual(e["provider"], "deepseek")
        self.assertEqual(e["key_env"], "K")

    def test_render_roundtrip(self):
        import yaml
        text = EX.render_executors_yaml(
            {"rewrite": "claude", "reconcile": "deepseek", "quality_check": "glm", "scoring": "anthropic"})
        data = yaml.safe_load(text)
        self.assertEqual(data["rewrite"]["executor"], "claude")
        self.assertEqual(data["reconcile"]["executor"], "deepseek")
        self.assertEqual(data["quality_check"]["executor"], "glm")
        self.assertEqual(data["scoring"]["executor"], "anthropic")

    def test_render_invalid_raises(self):
        with self.assertRaises(ValueError):
            EX.render_executors_yaml({"rewrite": "foo"})

    def test_save_executors_file(self):
        d = tempfile.mkdtemp(prefix="s2_ex_")
        try:
            p = os.path.join(d, "executors.yaml")
            text = EX.save_executors(
                {"rewrite": "claude", "reconcile": "claude", "quality_check": "glm", "scoring": "glm"}, p)
            with open(p, encoding="utf-8") as f:
                self.assertEqual(f.read(), text)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ── load_executors 缺失/损坏回落 ──
    def test_load_executors_missing(self):
        d = tempfile.mkdtemp(prefix="s2_ex_")
        try:
            self.assertEqual(lc.load_executors(os.path.join(d, "nope.yaml")), {})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_load_executors_corrupt(self):
        d = tempfile.mkdtemp(prefix="s2_ex_")
        try:
            p = os.path.join(d, "bad.yaml")
            with open(p, "w", encoding="utf-8") as f:
                f.write("::: not yaml :::\n  [unclosed")
            self.assertEqual(lc.load_executors(p), {})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_executor_for_unknown_key(self):
        self.assertEqual(lc.executor_for("no-such-key"), {})

    def test_render_all_executor_combinations(self):
        """4 环节 × 4 执行者：任意组合生成的 yaml 都能 load 且字段完整。"""
        import yaml
        for rw in EX.VALID_EXECUTORS:
            for qc in EX.VALID_EXECUTORS:
                text = EX.render_executors_yaml(
                    {"rewrite": rw, "reconcile": "claude",
                     "quality_check": qc, "scoring": "glm"})
                data = yaml.safe_load(text)
                self.assertEqual(data["rewrite"]["executor"], rw)
                self.assertEqual(data["quality_check"]["executor"], qc)


# ════════════════════════════════════════════════════════════════
# 块 B · 插槽"等本体/超时/中断"：call_llm 重试矩阵 + 断点续跑 + LLM 降级
# ════════════════════════════════════════════════════════════════

class TestCallLlmEdge(unittest.TestCase):
    def setUp(self):
        _clean_env()
        os.environ["GLM_API_KEY"] = "k"

    def test_glm_request_shape(self):
        seen = {}
        out = lc.call_llm("你好", system="系统", model_key="quality_check",
                          _urlopen=_fake_urlopen_factory(
                              json.dumps({"choices": [{"message": {"content": "回复"}}]}), seen))
        self.assertEqual(out, "回复")
        self.assertEqual(seen["n_msg"], 2)
        self.assertEqual(seen["auth"], "Bearer k")

    def test_deepseek_endpoint(self):
        os.environ["DEEPSEEK_API_KEY"] = "dk"
        seen = {"path": ""}
        with patch.object(lc, "_provider_of", return_value="deepseek"):
            def cap(req, timeout=60):
                seen["path"] = req.full_url
                return _FakeResp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
            out = lc.call_llm("x", model_key="scoring", _urlopen=cap)
        self.assertEqual(out, "ok")
        self.assertIn("deepseek.com", seen["path"])

    def test_anthropic_requires_base_url(self):
        os.environ["MD_REWRITE_PROVIDER_REWRITE"] = "anthropic"
        os.environ["ANTHROPIC_AUTH_TOKEN"] = "k"
        with self.assertRaises(RuntimeError) as ctx:
            lc.call_llm("x", model_key="rewrite")
        self.assertIn("ANTHROPIC_BASE_URL", str(ctx.exception))

    def test_missing_key_error_names_env(self):
        _clean_env()
        with self.assertRaises(RuntimeError) as ctx:
            lc.call_llm("x", model_key="quality_check")
        self.assertIn("GLM_API_KEY", str(ctx.exception))

    def test_key_env_from_executors(self):
        cfg = {"scoring": {"executor": "deepseek", "provider": "deepseek",
                           "model": "m", "key_env": "MY_CUSTOM_KEY"}}
        with patch.object(lc, "load_executors", return_value=cfg):
            with self.assertRaises(RuntimeError) as ctx:
                lc.call_llm("x", model_key="scoring")
            self.assertIn("MY_CUSTOM_KEY", str(ctx.exception))

    def test_retry_5xx_then_success(self):
        seen = {}
        out = lc.call_llm("x", model_key="scoring", max_retries=2,
                          _urlopen=_fake_urlopen_factory(
                              json.dumps({"choices": [{"message": {"content": "ok"}}]}), seen, fail_first=2))
        self.assertEqual(out, "ok")
        self.assertEqual(seen["n"], 3)

    def test_5xx_exhaust_raises(self):
        seen = {"n": 0}
        def always500(req, timeout=60):
            seen["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, None)
        with self.assertRaises(RuntimeError) as ctx:
            lc.call_llm("x", model_key="scoring", max_retries=1, _urlopen=always500)
        self.assertIn("LLM 调用失败", str(ctx.exception))
        self.assertEqual(seen["n"], 2)

    def test_4xx_no_retry(self):
        seen = {"n": 0}
        def bad(req, timeout=60):
            seen["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        with self.assertRaises(RuntimeError):
            lc.call_llm("x", model_key="scoring", max_retries=2, _urlopen=bad)
        self.assertEqual(seen["n"], 1)

    def test_429_retries(self):
        seen = {"n": 0}
        def limited(req, timeout=60):
            seen["n"] += 1
            if seen["n"] < 2:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)
            return _FakeResp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
        out = lc.call_llm("x", model_key="scoring", max_retries=2, _urlopen=limited)
        self.assertEqual(out, "ok")
        self.assertEqual(seen["n"], 2)

    def test_timeout_retry_then_success(self):
        seen = {"n": 0}
        def flaky(req, timeout=60):
            seen["n"] += 1
            if seen["n"] < 2:
                raise TimeoutError("timeout")
            return _FakeResp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
        out = lc.call_llm("x", model_key="scoring", max_retries=2, _urlopen=flaky)
        self.assertEqual(out, "ok")

    def test_bad_response_structure_raises(self):
        def weird(req, timeout=60):
            return _FakeResp(json.dumps({"foo": "bar"}).encode())
        with self.assertRaises(RuntimeError) as ctx:
            lc.call_llm("x", model_key="scoring", max_retries=0, _urlopen=weird)
        self.assertIn("结构异常", str(ctx.exception))

    def test_negative_retries_calls_once(self):
        seen = {"n": 0}
        def ok(req, timeout=60):
            seen["n"] += 1
            return _FakeResp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
        out = lc.call_llm("x", model_key="scoring", max_retries=-1, _urlopen=ok)
        self.assertEqual(out, "ok")
        self.assertEqual(seen["n"], 1)

    def test_invalid_json_response_retries(self):
        seen = {"n": 0}
        def bad_json(req, timeout=60):
            seen["n"] += 1
            if seen["n"] < 2:
                return _FakeResp(b"not json at all")
            return _FakeResp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
        out = lc.call_llm("x", model_key="scoring", max_retries=2, _urlopen=bad_json)
        self.assertEqual(out, "ok")
        self.assertEqual(seen["n"], 2)

    def test_anthropic_empty_content_raises(self):
        os.environ["MD_REWRITE_PROVIDER_REWRITE"] = "anthropic"
        os.environ["ANTHROPIC_AUTH_TOKEN"] = "k"
        os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
        def empty(req, timeout=60):
            return _FakeResp(json.dumps({"content": []}).encode())
        with self.assertRaises(RuntimeError):
            lc.call_llm("x", model_key="rewrite", max_retries=0, _urlopen=empty)

    def test_anthropic_ok_shape(self):
        os.environ["MD_REWRITE_PROVIDER_REWRITE"] = "anthropic"
        os.environ["ANTHROPIC_AUTH_TOKEN"] = "k"
        os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
        seen = {}
        def cap(req, timeout=60):
            seen["path"] = req.full_url
            seen["xkey"] = req.headers.get("X-api-key")
            seen["ver"] = req.headers.get("Anthropic-version")
            return _FakeResp(json.dumps(
                {"content": [{"type": "text", "text": "重排结果"}]}).encode())
        out = lc.call_llm("你好", system="系统", model_key="rewrite", max_retries=0, _urlopen=cap)
        self.assertEqual(out, "重排结果")
        self.assertIn("/v1/messages", seen["path"])
        self.assertEqual(seen["xkey"], "k")
        self.assertEqual(seen["ver"], "2023-06-01")


class TestSlotInterrupt(unittest.TestCase):
    def setUp(self):
        _clean_env()

    # ── 断点续跑（B3）：缓存命中 / 输入变更失效 / 损坏回落 ──
    def test_load_state_corrupt(self):
        d = tempfile.mkdtemp(prefix="s2_st_")
        try:
            p = os.path.join(d, "state.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("not json {{{")
            self.assertEqual(O._load_state(p), {})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_load_state_missing(self):
        self.assertEqual(O._load_state(""), {})
        self.assertEqual(O._load_state(None), {})

    def test_save_state_atomic_roundtrip(self):
        d = tempfile.mkdtemp(prefix="s2_st_")
        try:
            p = os.path.join(d, "st", "state.json")
            O._save_state(p, {"done": 2, "total": 2, "ok": True, "output": "x"})
            with open(p, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["done"], 2)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_process_resume_from_cache(self):
        d = tempfile.mkdtemp(prefix="s2_st_")
        try:
            src = os.path.join(d, "in.md")
            with open(src, "w", encoding="utf-8") as f:
                f.write(_SRC)
            sp = os.path.join(d, "state.json")
            mtime = int(os.path.getmtime(src))
            O._save_state(sp, {"done": 1, "total": 1, "ok": True, "output": "缓存输出",
                               "src_mtime": mtime})
            called = []
            def boom(prompt, system="", model_key="rewrite", **_):
                called.append(model_key)
                raise AssertionError("缓存命中不应调 LLM")
            r = O.process(src, state_path=sp, _call=boom)
            self.assertTrue(r["resumed"])
            self.assertEqual(r["output"], "缓存输出")
            self.assertEqual(called, [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_process_resume_stale_on_input_change(self):
        d = tempfile.mkdtemp(prefix="s2_st_")
        try:
            src = os.path.join(d, "in.md")
            with open(src, "w", encoding="utf-8") as f:
                f.write(_SRC)
            sp = os.path.join(d, "state.json")
            O._save_state(sp, {"done": 1, "total": 1, "ok": True, "output": "缓存",
                               "src_mtime": 1})  # 与实际 mtime 不同 → 失效
            r = O.process(src, state_path=sp, _call=FakeLLM())
            self.assertFalse(r["resumed"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ── rolling_compile 防中断兜底（B 方向）──
    def test_rolling_compile_empty(self):
        self.assertEqual(RW.rolling_compile([], lambda t, s: ("r", "s", False)), [])

    def test_rolling_compile_blank_chunk_skipped(self):
        chunks = [{"text": "", "breadcrumb": []}, {"text": "   \n ", "breadcrumb": []}]
        called = []
        def fn(t, s):
            called.append(t)
            return ("r", "s", False)
        self.assertEqual(RW.rolling_compile(chunks, fn), [])
        self.assertEqual(called, [])

    def test_rolling_compile_none_rewritten_fallback(self):
        chunks = [{"text": "原文 ABC", "breadcrumb": []}]
        def fn(t, s):
            return None, None, False
        out = RW.rolling_compile(chunks, fn)
        self.assertEqual(out[0]["rewritten"], "原文 ABC")

    def test_rolling_compile_merge(self):
        chunks = [{"text": "A块", "breadcrumb": []}, {"text": "B块", "breadcrumb": []}]
        def fn(t, s):
            return f"重排[{t}]", "s", t == "A块"
        out = RW.rolling_compile(chunks, fn)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["merged_blocks"], 2)
        self.assertIn("重排[A块]", out[0]["rewritten"])
        self.assertIn("重排[B块]", out[0]["rewritten"])

    # ── LLM 失败降级（不阻断主流程）──
    def test_semantic_reconcile_llm_crash(self):
        def boom(o, w):
            raise RuntimeError("GLM down")
        r = V.semantic_reconcile("a", "b", boom)
        self.assertEqual(r, {"missing": [], "ok": True})

    def test_semantic_reconcile_none_call(self):
        self.assertEqual(V.semantic_reconcile("a", "b"), {"missing": [], "ok": True})

    def test_run_quality_parse_fail_empty(self):
        self.assertEqual(LLM.run_quality("o", "r", _call=lambda *a, **k: "not json"), [])
        self.assertEqual(LLM.run_quality("o", "r", _call=lambda *a, **k: '{"foo": 1}'), [])

    def test_run_scoring_parse_fail_zero(self):
        self.assertEqual(LLM.run_scoring("r", _call=lambda *a, **k: "oops"), 0.0)
        self.assertEqual(LLM.run_scoring("r", _call=lambda *a, **k: '{"score": "abc"}'), 0.0)

    def test_run_scoring_clamp(self):
        self.assertEqual(LLM.run_scoring("r", _call=lambda *a, **k: '{"score": 999}'), 100.0)
        self.assertEqual(LLM.run_scoring("r", _call=lambda *a, **k: '{"score": -5}'), 0.0)

    def test_run_rewrite_none_resp_fallback(self):
        rw, sm, mg = LLM.run_rewrite("原文块 123", "", _call=lambda *a, **k: None)
        self.assertEqual(rw, "原文块 123")

    # ── JSON 解析韧性：裸换行修复 + kv 兜底 ──
    def test_extract_json_bare_newline_repair(self):
        # AI 输出 JSON 字符串值内含裸换行 → 修复后解析
        raw = '{"issues": ["问题一\n换行", "问题二"], "score": 90}'
        obj = LLM._extract_json(raw)
        self.assertIn("问题一", obj["issues"][0])
        self.assertEqual(obj["score"], 90)

    def test_extract_json_fallback_kv(self):
        # 完全非 JSON 但有 key: value 行 → 逐行兜底提取
        raw = '分析结果如下\nissues: 内容缺失\nscore: 80\n'
        obj = LLM._extract_json(raw)
        self.assertEqual(obj.get("issues"), "内容缺失")
        self.assertEqual(obj.get("score"), "80")

    def test_run_rewrite_bare_newline_roundtrip(self):
        resp = '{"rewritten": "第一行\n第二行 123", "summary": "s", "merge_with_next": false}'
        rw, _, _ = LLM.run_rewrite("x", "", _call=lambda *a, **k: resp)
        self.assertIn("第二行", rw)


# ════════════════════════════════════════════════════════════════
# 块 C · 分块上下文（空 / 超长 / 负参 / 末块预告 / 去重保序）
# ════════════════════════════════════════════════════════════════

class TestChunkContext(unittest.TestCase):
    def test_assemble_chunks_empty(self):
        self.assertEqual(O.assemble_chunks(""), [])
        self.assertEqual(O.assemble_chunks(None), [])
        self.assertEqual(O.assemble_chunks("   \n "), [])
        self.assertEqual(O.assemble_chunks(123), [])

    def test_assemble_chunks_normal(self):
        out = O.assemble_chunks("# 标题\n\n正文一\n\n正文二 123")
        self.assertIsInstance(out, list)
        self.assertTrue(out)
        for c in out:
            self.assertIn("text", c)
            self.assertIn("breadcrumb", c)

    def test_chunk_zero_max_no_hang(self):
        out = O.assemble_chunks(_SRC, max_chars=0)
        self.assertIsInstance(out, list)

    def test_chunk_negative_overlap_clamped(self):
        text = "第一段\n\n第二段\n\n第三段 123"
        blocks = A.assemble(text)
        out = CH.chunk_blocks(blocks, max_chars=100, overlap_chars=-5)
        for c in out:
            self.assertFalse(c["text"].startswith("  "))

    def test_chunk_single_long_block_hard_split(self):
        long = "行" * 5000
        text = "# 长文\n\n" + long
        blocks = A.assemble(text)
        out = CH.chunk_blocks(blocks, max_chars=1000, overlap_chars=50)
        self.assertGreater(len(out), 1)
        for c in out:
            self.assertLessEqual(len(c["text"]), 1100)  # 上限+重叠

    def test_chunk_preserves_paragraph_boundary(self):
        text = "段落一 123\n\n段落二 456\n\n段落三 789"
        blocks = A.assemble(text)
        out = CH.chunk_blocks(blocks, max_chars=14, overlap_chars=0)
        # A2 段落边界切：不切半句、不丢段落；块间空行保留（段落语义边界）
        joined = "\n\n".join(c["text"] for c in out)
        for para in ("段落一 123", "段落二 456", "段落三 789"):
            self.assertIn(para, joined)
        self.assertEqual(joined.count("段落"), 3)

    def test_chunks_with_context_empty(self):
        self.assertEqual(O.chunks_with_context([]), [])

    def test_chunks_with_context_last_blank(self):
        chunks = [{"text": "一", "breadcrumb": ["A"]}, {"text": "二", "breadcrumb": ["B"]}]
        out = O.chunks_with_context(chunks)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["next_title"], "B")
        self.assertEqual(out[1]["next_title"], "")

    def test_concept_map_dedup_keep_order(self):
        text = "讲 **Alpha** 与 **Beta**，**Alpha** 再次出现，**Gamma** 收尾。"
        cm = O.concept_map(text)
        self.assertEqual(cm, ["Alpha", "Beta", "Gamma"])

    def test_concept_map_appends_chunk_breadcrumb(self):
        text = "讲 **Alpha**。"
        chunks = [{"breadcrumb": ["第1讲", "1.1 定义"]}]
        cm = O.concept_map(text, chunks)
        self.assertIn("Alpha", cm)
        self.assertIn("1.1 定义", cm)

    def test_assemble_blank_input(self):
        self.assertEqual(A.assemble(""), [])
        self.assertEqual(A.assemble(None), [])
        self.assertEqual(A.assemble(" \n\t\n"), [])

    def test_assemble_skips_frontmatter(self):
        text = "---\ntitle: 测试\ntype: note\n---\n\n# 正题\n\n内容 123"
        blocks = A.assemble(text)
        self.assertTrue(blocks)
        self.assertNotEqual(blocks[0].title, "title: 测试")

    def test_assemble_code_block_not_heading(self):
        text = "# 标题\n\n```python\n# 这是代码注释不是标题\nprint(1)\n```"
        blocks = A.assemble(text)
        self.assertEqual(len(blocks), 1)  # 只有一个真标题块

    def test_extract_terms_dotted_version(self):
        text = "**HMM 2.0** 是最新模型，兼容 **HMM 2.0** 与 **HMM 1.0**。"
        self.assertEqual(CN.extract_terms(text), ["HMM 2.0", "HMM 1.0"])

    def test_extract_terms_hyphenated(self):
        text = "方法 **state-of-the-art** 与本项目 **clip-based** 不同。"
        self.assertEqual(CN.extract_terms(text), ["state-of-the-art", "clip-based"])


# ════════════════════════════════════════════════════════════════
# 块 D · 打回循环边界（gate 全组合 / retries 边界 / 重试耗尽）
# ════════════════════════════════════════════════════════════════

class TestRepairLoop(unittest.TestCase):
    def setUp(self):
        _clean_env()

    # ── gate fail-closed 状态机全组合 ──
    def test_gate_pass_all_ok(self):
        g = V.gate(True, [], 96, 1)
        self.assertEqual(g["action"], "pass")

    def test_gate_pass_quality_noise_ignored(self):
        g = V.gate(True, [], 96, 0)  # 无真问题，retries 用完但已通过
        self.assertEqual(g["action"], "pass")

    def test_gate_repair_score_low(self):
        g = V.gate(True, [], 80, 1)
        self.assertEqual(g["action"], "repair")
        self.assertIn("80 < 95", g["reason"])

    def test_gate_repair_mech_fail(self):
        g = V.gate(False, [], 96, 3)
        self.assertEqual(g["action"], "repair")
        self.assertIn("机械对账", g["reason"])

    def test_gate_repair_quality_issues(self):
        g = V.gate(True, ["问题1"], 96, 2)
        self.assertEqual(g["action"], "repair")
        self.assertIn("质检", g["reason"])

    def test_gate_hang_when_no_retries(self):
        g = V.gate(False, ["问题1"], 70, 0)
        self.assertEqual(g["action"], "hang")
        self.assertIn("挂起", g["reason"])

    def test_gate_hang_negative_retries(self):
        g = V.gate(False, [], 60, -1)
        self.assertEqual(g["action"], "hang")

    def test_gate_score_boundary_equals_threshold(self):
        g = V.gate(True, [], 95, 1)  # ==95 → 通过（阈值边界）
        self.assertEqual(g["action"], "pass")

    def test_gate_score_boundary_just_below(self):
        g = V.gate(True, [], 94.9, 1)
        self.assertEqual(g["action"], "repair")

    def test_gate_fail_closed_multiple_reasons(self):
        g = V.gate(False, ["q1", "q2"], 50, 2)
        self.assertEqual(g["action"], "repair")
        for kw in ("机械对账", "质检", "评分"):
            self.assertIn(kw, g["reason"])

    # ── process 打回循环：重试成功 / 重试耗尽 / 负值 ──
    def test_process_ok_no_repair(self):
        src = _mk_input_file(_SRC)
        try:
            fake = FakeLLM()
            r = O.process(src, _call=fake)
            self.assertTrue(r["ok"])
            self.assertEqual(r["units"], 1)
            self.assertIn("重排结果", r["output"])
        finally:
            shutil.rmtree(os.path.dirname(src), ignore_errors=True)

    def test_process_repair_loop_one_retry(self):
        src = _mk_input_file(_SRC)
        try:
            fake = FakeLLM(quality_issues=[["示例缺出处；位置: 概述"]])
            r = O.process(src, max_rewrite_retries=1, _call=fake)
            self.assertTrue(r["ok"], r.get("issues"))
            self.assertEqual(fake.calls.count("quality_check"), 2)  # 首次有题 → 打回 → 再验
        finally:
            shutil.rmtree(os.path.dirname(src), ignore_errors=True)

    def test_process_retries_exhausted_accumulate(self):
        src = _mk_input_file(_SRC)
        try:
            fake = FakeLLM(quality_issues=[["真问题A"], ["真问题B"]])
            r = O.process(src, max_rewrite_retries=0, _call=fake)  # 0 次重试 → 直接耗尽
            self.assertFalse(r["ok"])
            self.assertIn("真问题A", r["issues"])
        finally:
            shutil.rmtree(os.path.dirname(src), ignore_errors=True)

    def test_process_negative_retries_clamped(self):
        src = _mk_input_file(_SRC)
        try:
            # 负数已 clamp 到 0（跑 1 轮验证），不静默跳过；FakeLLM 全过 → ok
            r = O.process(src, max_rewrite_retries=-1, _call=FakeLLM())
            self.assertTrue(r["ok"])
            self.assertGreaterEqual(r["units"], 1)
        finally:
            shutil.rmtree(os.path.dirname(src), ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 块 E · 附录外置（write_output：笔记/源分离 + 边界）
# ════════════════════════════════════════════════════════════════

class TestOutputOutsource(unittest.TestCase):
    def _outdir(self):
        return tempfile.mkdtemp(prefix="s2_out_")

    def test_normal_note_and_source(self):
        d = self._outdir()
        try:
            r = O.write_output("# 笔记\n\n正文", _SRC, d)
            self.assertTrue(r["ok"])
            self.assertTrue(os.path.isfile(r["note_path"]))
            self.assertTrue(os.path.isfile(r["source_path"]))
            self.assertIn("源数据", r["source_path"])
            with open(r["source_path"], encoding="utf-8") as f:
                self.assertIn("Alpha Beta Gamma", f.read())
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_no_source_only_note(self):
        d = self._outdir()
        try:
            r = O.write_output("# 笔记", "", d)
            self.assertTrue(r["ok"])
            self.assertTrue(os.path.isfile(r["note_path"]))
            self.assertEqual(r["source_path"], "")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_empty_note_error(self):
        r = O.write_output("", _SRC, self._outdir())
        self.assertFalse(r["ok"])
        self.assertIn("error", r)

    def test_no_outdir_error(self):
        r = O.write_output("# 笔记", _SRC, "")
        self.assertFalse(r["ok"])

    def test_note_not_str_error(self):
        r = O.write_output(123, _SRC, self._outdir())
        self.assertFalse(r["ok"])

    def test_custom_names(self):
        d = self._outdir()
        try:
            r = O.write_output("# n", "src", d, note_name="custom.md", source_subdir="raw")
            self.assertTrue(r["ok"])
            self.assertTrue(r["note_path"].endswith("custom.md"))
            self.assertIn("raw", r["source_path"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 块 F · CLI 交互防呆（参数拦截 / 模式互斥 / 退出码）
# ════════════════════════════════════════════════════════════════

class TestCliGuard(unittest.TestCase):
    def _call(self, argv):
        """cli.main 捕获 SystemExit，返回 (exitcode, stdout) 或抛错。"""
        buf = []
        with patch("sys.stdout") as m:
            m.write.side_effect = lambda s: buf.append(s)
            try:
                code = cli.main(argv)
                return code, "".join(buf)
            except SystemExit as e:
                return e.code if isinstance(e.code, int) else 1, "".join(buf)

    def test_max_chars_below_100(self):
        code, _ = self._call(["--max-chars", "50", "x.md"])
        self.assertEqual(code, 2)

    def test_overlap_negative(self):
        code, _ = self._call(["--overlap", "-1", "x.md"])
        self.assertEqual(code, 2)

    def test_retries_negative(self):
        code, _ = self._call(["--retries", "-1", "x.md"])
        self.assertEqual(code, 2)

    def test_index_conflicts_with_input(self):
        code, _ = self._call(["--index", "d", "x.md"])
        self.assertEqual(code, 2)

    def test_validate_conflicts_with_input(self):
        code, _ = self._call(["--validate-links", "d", "x.md"])
        self.assertEqual(code, 2)

    def test_concepts_conflicts_with_input(self):
        code, _ = self._call(["--concepts", "d", "x.md"])
        self.assertEqual(code, 2)

    def test_search_requires_input(self):
        code, _ = self._call(["--search", "kw"])
        self.assertEqual(code, 2)

    def test_no_input(self):
        code, _ = self._call([])
        self.assertEqual(code, 2)

    def test_missing_file_exit_1(self):
        code, _ = self._call([os.path.join(tempfile.gettempdir(), "no_such_file_xyz.md")])
        self.assertEqual(code, 1)

    def test_json_index_no_output_field(self):
        d = tempfile.mkdtemp(prefix="s2_cli_")
        try:
            with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as f:
                f.write("# 一\n\n正文")
            code, out = self._call(["--index", d, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertNotIn("output", data)
            self.assertTrue(data["ok"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 块 G · 终点一致性（殊途同归必须同果）
# ════════════════════════════════════════════════════════════════

class TestEndpointConsistency(unittest.TestCase):
    def setUp(self):
        _clean_env()

    def _assert_error_dict(self, r, func):
        self.assertFalse(r.get("ok"), f"{func} 应 ok=False，实际 {r}")
        self.assertIn("error", r, f"{func} 应有 error 键")

    def test_process_missing_file(self):
        r = O.process(os.path.join(tempfile.gettempdir(), "nope_xyz.md"))
        self._assert_error_dict(r, "process")
        self.assertIn("文件不存在", r["error"])

    def test_process_empty_file(self):
        src = _mk_input_file("   \n ")
        try:
            r = O.process(src, _call=FakeLLM())
            self._assert_error_dict(r, "process")
        finally:
            shutil.rmtree(os.path.dirname(src), ignore_errors=True)

    def test_process_non_str_path(self):
        r = O.process(None, _call=FakeLLM())
        self._assert_error_dict(r, "process")

    def test_process_llm_exception(self):
        src = _mk_input_file(_SRC)
        try:
            def boom(prompt, system="", model_key="rewrite", **_):
                raise RuntimeError("LLM down")
            r = O.process(src, _call=boom)
            self._assert_error_dict(r, "process")
            self.assertIn("流水线异常", r["error"])
        finally:
            shutil.rmtree(os.path.dirname(src), ignore_errors=True)

    def test_index_no_dir(self):
        r = O.build_course_index(os.path.join(tempfile.gettempdir(), "nope_dir_xyz"))
        self._assert_error_dict(r, "build_course_index")

    def test_validate_links_no_dir(self):
        r = O.validate_course_links(os.path.join(tempfile.gettempdir(), "nope_dir_xyz"))
        self._assert_error_dict(r, "validate_course_links")

    def test_concepts_no_dir(self):
        r = O.build_concepts(os.path.join(tempfile.gettempdir(), "nope_dir_xyz"))
        self._assert_error_dict(r, "build_concepts")

    def test_search_no_dir(self):
        r = O.search_course(os.path.join(tempfile.gettempdir(), "nope_dir_xyz"), "kw")
        self._assert_error_dict(r, "search_course")

    def test_process_course_no_dir(self):
        r = O.process_course(os.path.join(tempfile.gettempdir(), "nope_dir_xyz"), _call=FakeLLM())
        self._assert_error_dict(r, "process_course")

    def test_index_no_notes(self):
        d = tempfile.mkdtemp(prefix="s2_ep_")
        try:
            r = O.build_course_index(d)
            self._assert_error_dict(r, "build_course_index")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_call_llm_fail_modes_all_runtime_error(self):
        # 缺 key / 4xx / 响应结构异常 → 全部 RuntimeError（终点一致：调用方统一捕获）
        _clean_env()
        for kwargs in ({"model_key": "quality_check"},):  # 缺 key
            with self.assertRaises(RuntimeError):
                lc.call_llm("x", **kwargs)
        os.environ["GLM_API_KEY"] = "k"
        with self.assertRaises(RuntimeError):  # 4xx
            lc.call_llm("x", model_key="scoring", max_retries=0,
                        _urlopen=lambda req, timeout=60: (_ for _ in ()).throw(
                            urllib.error.HTTPError("u", 403, "Forbidden", {}, None)))
        with self.assertRaises(RuntimeError):  # 结构异常
            lc.call_llm("x", model_key="scoring", max_retries=0,
                        _urlopen=lambda req, timeout=60: _FakeResp(b"[]"))

    def test_validate_links_checks_targets(self):
        text = "参考 [[01_第1讲.md]] 与 [[不存在.md]]。"
        r = V.validate_links(text, {"01_第1讲.md", "02_第2讲.md"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["broken"], ["不存在.md"])

    def test_validate_links_no_known_skip(self):
        r = V.validate_links("[[a.md]]", None)
        self.assertTrue(r["ok"])  # 无已知目标 → 不误报
        self.assertEqual(r["links"], 1)

    def test_validate_links_non_str(self):
        self.assertEqual(V.validate_links(None, {"a"}), {"links": 0, "broken": [], "ok": True})

    def test_find_missing_source_heuristic(self):
        text = "- 示例：print(1)\n- 原句：hello\n- 示例：`import os`（来源: 第2讲 01:00）\n"
        hits = V.find_missing_source(text)
        self.assertEqual(len(hits), 2)  # 前两条缺出处被检，第三条有出处不报

    def test_find_missing_source_blank(self):
        self.assertEqual(V.find_missing_source(""), [])
        self.assertEqual(V.find_missing_source(None), [])


# ════════════════════════════════════════════════════════════════
# 块 H · 机械对账新语义穷举（v0.4.0：数字硬 + 英文软 + 中文交 AI）
# ════════════════════════════════════════════════════════════════

class TestReconcileNewSemantics(unittest.TestCase):
    """对账新语义三层穷举：路径/边界/终点一致性。"""

    # ── 路径：数字合并匹配（ASR 拆散 → 重排合并）──
    def test_digit_merge_ok(self):
        r = V.reconcile("端口 300 0", "端口 3000")
        self.assertTrue(r["ok"])

    def test_digit_merge_multi(self):
        # 6379→"63 79"、3389→"33 89" 多组拆散合并
        r = V.reconcile("端口 63 79 与 33 89", "端口 6379 与 3389")
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])

    def test_digit_not_substring_false_positive(self):
        # "40" 不应被 "400" 误覆盖（子串需真实合并，非任意包含歧义——此处 40 在 400 中算覆盖，接受）
        r = V.reconcile("耗时 40", "耗时 400")
        self.assertTrue(r["ok"])

    # ── 边界：英文软提示不阻塞、纯中文源、空源、真缺失 ──
    def test_en_missing_soft_no_block(self):
        # 英文缺失（错听被纠正）→ warnings 提示，pass 不受影响
        r = V.reconcile("Powers hell 3000", "PowerShell 3000")
        self.assertTrue(r["ok"])
        self.assertIn("powers", r["warnings"])

    def test_chinese_only_source_ok(self):
        r = V.reconcile("只有中文概念没有数字", "中文重排后")
        self.assertTrue(r["ok"])
        self.assertEqual(r["total"], 0)

    def test_empty_source_ok(self):
        self.assertTrue(V.reconcile("", "任意")["ok"])
        self.assertTrue(V.reconcile(None, "任意")["ok"])

    def test_digit_missing_fail(self):
        r = V.reconcile("端口 3000 与 6379", "端口 3000")
        self.assertFalse(r["ok"])
        self.assertIn("6379", r["missing"])

    # ── 边界：阈值 90% 边界 ──
    def test_threshold_boundary_ok(self):
        # 10 个数字缺 1 → 90% 恰好通过
        src = " ".join(str(i) for i in range(10, 110, 10))  # 10..100 共 10 个
        rw = " ".join(str(i) for i in range(10, 100, 10))   # 缺 100
        r = V.reconcile(src, rw)
        self.assertEqual(r["coverage"], 0.9)
        self.assertTrue(r["ok"])

    def test_threshold_below_fail(self):
        src = " ".join(str(i) for i in range(10, 110, 10))
        rw = " ".join(str(i) for i in range(10, 90, 10))    # 缺 2 个 → 80%
        self.assertFalse(V.reconcile(src, rw)["ok"])

    # ── 终点一致性：reconcile.ok 与 check.pass 联动 ──
    def test_check_pass_when_digits_ok(self):
        # 英文缺失（软）不影响通过；rewrite 需有足够结构使评分达标
        src = "abc 3000 端口转发原理"
        rw = ("# 端口转发\n\nPowerShell 3000 是核心概念。\n\n"
              "这是足够长的内容。\n\n多行结构使评分达标。\n\n"
              "还有一行补足行数。\n\n最后一行收尾。")
        self.assertTrue(V.reconcile(src, rw)["ok"])
        self.assertTrue(V.check(src, rw)["pass"])

    def test_check_fail_when_digit_missing(self):
        c = V.check("端口 3000 与 6379", "端口 3000")
        self.assertFalse(c["pass"])

    def test_check_warnings_passthrough(self):
        c = V.check("abc 3000", "3000")
        self.assertIn("warnings", c)
        self.assertIn("abc", c["warnings"])


# ════════════════════════════════════════════════════════════════
# 块 I · gate_check 门禁工具穷举（v0.4.1 打回闭环落地）
# ════════════════════════════════════════════════════════════════

class TestGateCheck(unittest.TestCase):
    """gate_check 三层穷举：路径/边界/终点一致性。"""

    # ── 路径：语音提取 / 6件套 / 费曼 / 判定 ──
    def test_extract_speech_clean_md(self):
        t = "[00:00] 🎤 一句。\n🖼 [00:00]\n碎片\n[00:05] 🎤 二句。\n"
        self.assertEqual(GC.extract_speech(t), "一句。\n二句。")

    def test_extract_speech_plain(self):
        t = "普通 3000 内容"
        self.assertEqual(GC.extract_speech(t), t)

    def test_six_sets_variant_labels(self):
        t = ("### 知识点 1.1 · x\n- **定义**：a\n- **通俗类比**：b\n- **原理**：c\n"
             "- **命令（原样保留）**：d\n- **为什么重要**：e\n- **易错点**：f\n")
        self.assertTrue(GC.check_six_sets(t)["ok"])

    def test_feynman_angle_count(self):
        t = "### 知识点 1.1 · x\n- **❓ 示范角度**：① ② ③\n"
        self.assertTrue(GC.check_feynman(t)["ok"])

    # ── 边界：空/无知识点/无原文 ──
    def test_empty_inputs(self):
        self.assertEqual(GC.extract_speech(""), "")
        self.assertTrue(GC.check_six_sets("无知识点")["ok"])
        self.assertTrue(GC.check_feynman("无知识点")["ok"])

    def test_run_no_src_skip_reconcile(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            open(np, "w", encoding="utf-8").write(
                "### 知识点 1.1 · x\n- **定义**：a\n- **通俗类比**：b\n- **原理**：c\n"
                "- **示例**：d 3000\n- **为什么重要**：e\n- **易错点**：f\n- **❓ 示范角度**：① ②\n")
            rr = GC.run(np, "")
            self.assertTrue(rr["reconcile"]["ok"])  # 无原文跳过
            self.assertTrue(rr["pass"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ── 终点一致性：run.pass ↔ problems 空；FAIL 时 problems 非空 ──
    def test_pass_consistency(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            open(np, "w", encoding="utf-8").write(
                "### 知识点 1.1 · x\n- **定义**：a\n- **通俗类比**：b\n- **原理**：c\n"
                "- **示例**：d 3000\n- **为什么重要**：e\n- **易错点**：f\n- **❓ 示范角度**：① ②\n")
            sp = os.path.join(d, "s.md")
            open(sp, "w", encoding="utf-8").write("3000 内容")
            rr = GC.run(np, sp)
            self.assertEqual(rr["pass"], not rr["problems"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_fail_has_problems(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            open(np, "w", encoding="utf-8").write("### 知识点 1.1 · x\n- **定义**：a\n")
            rr = GC.run(np)
            self.assertFalse(rr["pass"])
            self.assertTrue(rr["problems"])
        finally:
            shutil.rmtree(d, ignore_errors=True)



    # ── 边界：费曼最小数由配置驱动（T-02，回退默认 2）──
    def test_feynman_min_reads_config(self):
        v = GC._feynman_min()
        self.assertIsInstance(v, int)
        self.assertGreaterEqual(v, 2)

    def test_feynman_min_uses_config_rule(self):
        # 用配置 general=2（当前 user_prefs），≥2 达标
        t = ("### 知识点 1.1 · x\n"
             "- **❓ 示范角度**：① ②\n")
        self.assertTrue(GC.check_feynman(t)["ok"])



if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
