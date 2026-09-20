"""providers/llm_client.py — LLM 调用封装（GLM/DeepSeek，OpenAI 兼容）。

职责：模型名从 configs/models.yaml 读（环境变量可覆盖），API Key 从环境变量读，
统一走 OpenAI 兼容 HTTP 接口，带超时 + 重试。不藏业务逻辑。

环境变量：
  GLM_API_KEY / DEEPSEEK_API_KEY      各供应商 Key
  MD_REWRITE_MODEL_<KEY>              覆盖 models.yaml 的模型名（KEY 大写）
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

# 供应商 OpenAI 兼容 base URL（含聊天补全路径）
_ENDPOINTS = {
    "glm": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    # anthropic 通道 endpoint 从环境变量 ANTHROPIC_BASE_URL 读（可指向官方或代理），不硬编码
}
_KEY_ENV = {"glm": "GLM_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
            "anthropic": "ANTHROPIC_AUTH_TOKEN"}
# 供应商路由（默认）：rewrite/reconcile → 本体/anthropic 通道；
# quality_check/scoring → GLM（质检/评分与生成分离，且不误找 DeepSeek key）
# 供应商路由（实测定案）：全走 GLM 直连（稳定能跑通）。
# anthropic 通道代码保留能力——配好 ANTHROPIC_BASE_URL/AUTH_TOKEN 或设 MD_REWRITE_PROVIDER_<KEY> 即可启用
_MODEL_KEY_MAP = {"rewrite": "glm", "reconcile": "glm",
                  "quality_check": "glm", "scoring": "glm"}
# 执行者类型 → 供应商（executors.yaml 里 executor 字段映射到 provider）
_EXECUTOR_PROVIDER = {"glm": "glm", "deepseek": "deepseek",
                      "anthropic": "anthropic", "claude": "anthropic"}
_ANTHROPIC_VERSION = "2023-06-01"
_ANTHROPIC_MAX_TOKENS = 8192  # Claude 通道 Messages API 必填 max_tokens（重排输出可能较长）
# 默认模型（models.yaml 缺失时兜底；不硬编码在业务代码里，集中在这）
_DEFAULT_MODELS = {"rewrite": "glm-4.5-air", "quality_check": "glm-4.5-air",
                   "reconcile": "glm-4.5-air", "scoring": "glm-4.5-air"}


class _PostRedirect(urllib.request.HTTPRedirectHandler):
    """重定向时保持 POST（urllib 默认 302→GET，会丢 body 导致 LLM 报 'GET not supported'）。

    大请求（完整 spec + 长块）可能触发 LLM 侧 302 重定向；保持 POST + body + headers 跟随。
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and getattr(req, "method", "") == "POST":
            new.method = "POST"
            new.data = req.data
            for k, v in req.headers.items():
                new.headers[k] = v
        return new


def _build_opener():
    return urllib.request.build_opener(_PostRedirect())


def load_models_config(config_path: str | None = None) -> dict:
    """读 configs/models.yaml。缺失/损坏 → 内置默认（不阻断）。"""
    import yaml  # noqa: WPS433 (仅此处需 yaml)

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs", "models.yaml")
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return dict(_DEFAULT_MODELS)
        return data
    except Exception:  # noqa: BLE001 配置缺失不阻断
        return dict(_DEFAULT_MODELS)


def load_executors(config_path: str | None = None) -> dict:
    """读 configs/executors.yaml（v0.3.0 执行者选择器）。缺失/损坏 → {}（回落内置路由）。"""
    import yaml  # noqa: WPS433

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs", "executors.yaml")
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 配置缺失不阻断
        return {}


def executor_for(model_key: str) -> dict:
    """返回某环节的执行者配置 {executor, provider, model, key_env}；无配置 → {}。

    v0.3.0：每环节可选执行者（本体/GLM/DeepSeek/Anthropic），覆盖内置路由。
    """
    execs = load_executors()
    return execs.get(model_key, {}) if isinstance(execs, dict) else {}


def resolve_model(model_key: str, config_path: str | None = None) -> str:
    """按 model_key（rewrite/quality_check/scoring）解析最终模型名。

    优先级：环境变量 MD_REWRITE_MODEL_<KEY> > executors.yaml（该环节 model）
    > models.yaml > 内置默认。None/未知 key → 回落内置默认（不崩）。
    """
    model_key = model_key or "rewrite"
    env = os.environ.get(f"MD_REWRITE_MODEL_{model_key.upper()}")
    if env:
        return env
    ex = executor_for(model_key)
    if ex.get("model"):
        return ex["model"]
    cfg = load_models_config(config_path)
    return (cfg.get(model_key) or _DEFAULT_MODELS.get(model_key)
            or _DEFAULT_MODELS["rewrite"])


def _provider_of(model_key: str) -> str:
    """模型键 → 供应商（决定 endpoint/key env）。

    优先级：环境变量 MD_REWRITE_PROVIDER_<KEY> > executors.yaml（executor/provider）
    > 内置路由 _MODEL_KEY_MAP。
    """
    env = os.environ.get(f"MD_REWRITE_PROVIDER_{str(model_key or '').upper()}")
    if env:
        return env
    ex = executor_for(model_key)
    if ex.get("provider"):
        return ex["provider"]
    if ex.get("executor") in _EXECUTOR_PROVIDER:
        return _EXECUTOR_PROVIDER[ex["executor"]]
    return _MODEL_KEY_MAP.get(model_key, "glm")


def call_llm(prompt: str, system: str = "", model_key: str = "rewrite",
             max_retries: int = 2, timeout: int = 180,
             _urlopen=urllib.request.urlopen) -> str:
    """调用 LLM（OpenAI 兼容），带超时 + 重试。返回回复文本；全失败抛异常。

    Args:
        prompt: 用户消息。
        system: 系统提示（可空）。
        model_key: rewrite/quality_check/scoring。
        max_retries: 重试次数（超时/5xx 才重试；4xx 不重试）。
        timeout: 单次请求超时秒数。
        _urlopen: 可注入的 urlopen（测试用）。
    """
    provider = _provider_of(model_key)
    max_retries = max(0, max_retries)  # 负数 → 0（至少调用 1 次，不直接跳过）
    # key_env 优先读 executors.yaml（执行者选择器），否则按供应商默认
    key_env = executor_for(model_key).get("key_env") or _KEY_ENV[provider]
    api_key = os.environ.get(key_env, "")
    if not api_key:
        raise RuntimeError(f"缺少环境变量 {key_env}（LLM 调用前须配置）")
    model = resolve_model(model_key)
    if provider == "anthropic":
        # Claude 通道（Anthropic Messages 协议，endpoint 可指向官方或兼容代理）
        base = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
        if not base:
            raise RuntimeError("缺少 ANTHROPIC_BASE_URL（Claude 通道）")
        url = base + "/v1/messages"
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        body = json.dumps({
            "model": model,
            "max_tokens": _ANTHROPIC_MAX_TOKENS,
            "messages": messages,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={
                                         "Content-Type": "application/json",
                                         "x-api-key": api_key,
                                         "anthropic-version": _ANTHROPIC_VERSION,
                                         "Authorization": f"Bearer {api_key}",
                                     })
    else:
        # OpenAI 兼容（GLM/DeepSeek）
        url = _ENDPOINTS[provider]
        body = json.dumps({
            "model": model,
            "messages": [m for m in
                         ([{"role": "system", "content": system}] if system else [])
                         + [{"role": "user", "content": prompt}]],
            "temperature": 0.3,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={
                                         "Content-Type": "application/json",
                                         "Authorization": f"Bearer {api_key}",
                                     })
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with _urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            try:
                if provider == "anthropic":
                    # Messages 响应：content 数组取 text 拼接（可能含 thinking）
                    items = data.get("content", [])
                    texts = [it.get("text", "") for it in items
                             if isinstance(it, dict) and it.get("type") == "text"]
                    if texts:
                        return "\n".join(texts)
                    if items and isinstance(items[0], dict):
                        return items[0].get("text", "")
                    raise RuntimeError(
                        f"LLM response 无文本内容: {str(data)[:120]}")
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                raise RuntimeError(
                    f"LLM response 结构异常（缺 choices/message/content）: {str(data)[:120]}") from None
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:  # 4xx 除 429 外不重试（参数/鉴权错）；429 限流应重试
                raise RuntimeError(f"LLM HTTP {e.code}: {e.reason}") from e
            last_err = e
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as e:
            last_err = e
        if attempt < max_retries:
            time.sleep(1.0 * (attempt + 1))  # 退避重试
    raise RuntimeError(f"LLM 调用失败（重试 {max_retries} 次后）：{last_err}") from last_err
