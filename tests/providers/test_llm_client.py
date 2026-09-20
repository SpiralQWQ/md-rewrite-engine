# -*- coding: utf-8 -*-
"""providers/llm_client 单元测试：模型解析 / 缺 Key / mock 调用 / 重试。"""
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from providers import llm_client as lc  # noqa: E402


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestLlmClient(unittest.TestCase):
    def setUp(self):
        os.environ.pop("GLM_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("MD_REWRITE_MODEL_REWRITE", None)
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        os.environ.pop("ANTHROPIC_BASE_URL", None)
        os.environ.pop("MD_REWRITE_PROVIDER_REWRITE", None)

    def test_resolve_from_config(self):
        # 执行者选择器（executors.yaml 优先）：rewrite=本体(claude)，quality=GLM
        self.assertEqual(lc.resolve_model("rewrite"), "claude-sonnet-4-5")
        self.assertEqual(lc.resolve_model("quality_check"), "glm-4.5-air")

    def test_resolve_env_override(self):
        os.environ["MD_REWRITE_MODEL_REWRITE"] = "glm-test"
        self.assertEqual(lc.resolve_model("rewrite"), "glm-test")

    def test_missing_key_error(self):
        # quality_check 走 GLM：缺 GLM key 报错
        with self.assertRaises(RuntimeError) as ctx:
            lc.call_llm("hi", model_key="quality_check")
        self.assertIn("GLM_API_KEY", str(ctx.exception))

    def test_call_ok(self):
        os.environ["GLM_API_KEY"] = "k"
        seen = {}

        def fake_urlopen(req, timeout=60):
            body = json.loads(req.data.decode())
            seen["model"] = body.get("model")
            seen["n_msg"] = len(body.get("messages", []))
            seen["auth"] = req.headers.get("Authorization")
            return _FakeResp(json.dumps({"choices": [{"message": {"content": "回复"}}]}).encode())

        out = lc.call_llm("你好", system="系统", model_key="quality_check", _urlopen=fake_urlopen)
        self.assertEqual(out, "回复")
        self.assertEqual(seen["model"], "glm-4.5-air")
        self.assertEqual(seen["n_msg"], 2)
        self.assertEqual(seen["auth"], "Bearer k")

    def test_call_ok_anthropic(self):
        """anthropic 通道能力（Messages 协议，配好环境变量后可启用）。"""
        os.environ["MD_REWRITE_PROVIDER_REWRITE"] = "anthropic"  # 强制 rewrite 走 anthropic
        os.environ["ANTHROPIC_AUTH_TOKEN"] = "k"
        os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9999"
        seen = {}

        def fake_urlopen(req, timeout=60):
            body = json.loads(req.data.decode())
            seen["path"] = req.full_url
            seen["model"] = body.get("model")
            seen["max_tokens"] = body.get("max_tokens")
            seen["n_msg"] = len(body.get("messages", []))
            seen["xkey"] = req.headers.get("X-api-key")
            seen["ver"] = req.headers.get("Anthropic-version")
            return _FakeResp(json.dumps(
                {"content": [{"type": "text", "text": "重排结果"}]}).encode())

        out = lc.call_llm("你好", system="系统", model_key="rewrite", _urlopen=fake_urlopen)
        self.assertEqual(out, "重排结果")
        # model 名由 resolve_model 决定（与通道独立）；通道能力看 path/xkey/ver/max_tokens
        self.assertEqual(seen["model"], lc.resolve_model("rewrite"))
        self.assertIn("/v1/messages", seen["path"])
        self.assertEqual(seen["max_tokens"], lc._ANTHROPIC_MAX_TOKENS)
        self.assertEqual(seen["n_msg"], 2)  # system + user
        self.assertEqual(seen["xkey"], "k")
        self.assertEqual(seen["ver"], "2023-06-01")

    def test_retry_then_success(self):
        os.environ["GLM_API_KEY"] = "k"
        calls = {"n": 0}

        def flaky(req, timeout=60):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, None)
            return _FakeResp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

        out = lc.call_llm("x", model_key="quality_check", max_retries=2, _urlopen=flaky)
        self.assertEqual(out, "ok")
        self.assertEqual(calls["n"], 3)

    def test_4xx_no_retry(self):
        os.environ["GLM_API_KEY"] = "k"
        calls = {"n": 0}

        def bad(req, timeout=60):
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

        with self.assertRaises(RuntimeError):
            lc.call_llm("x", model_key="quality_check", max_retries=2, _urlopen=bad)
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
