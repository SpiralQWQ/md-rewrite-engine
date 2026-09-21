"""providers/executors.py — 执行者配置生成（v0.3.0 执行者选择器）。

对话询问 4 环节（rewrite/reconcile/quality_check/scoring）各由谁做 → 生成/更新
configs/executors.yaml。执行者类型：claude(本体)/glm/deepseek/anthropic。
"""
from __future__ import annotations

import os

# ── 有效执行者类型 ──
VALID_EXECUTORS = ("claude", "glm", "deepseek", "anthropic")
_KEYS = ("rewrite", "reconcile", "quality_check", "scoring")

# 每类执行者的默认 provider/model/key_env
_EXECUTOR_DEFAULTS = {
    "claude": {"executor": "claude", "provider": "anthropic",
               "model": "claude-sonnet-4-5", "key_env": "ANTHROPIC_AUTH_TOKEN"},
    "glm": {"executor": "glm", "provider": "glm",
            "model": "glm-4.5-air", "key_env": "GLM_API_KEY"},
    "deepseek": {"executor": "deepseek", "provider": "deepseek",
                 "model": "deepseek-chat", "key_env": "DEEPSEEK_API_KEY"},
    "anthropic": {"executor": "anthropic", "provider": "anthropic",
                  "model": "claude-sonnet-4-5", "key_env": "ANTHROPIC_AUTH_TOKEN"},
}


def validate_executor(executor) -> bool:
    """校验执行者类型是否合法。"""
    return isinstance(executor, str) and executor in VALID_EXECUTORS


def build_executor_entry(executor: str, model: str = "", provider: str = "",
                         key_env: str = "") -> dict:
    """按执行者类型生成条目；可覆盖 model/provider/key_env。非法 → {}。"""
    if not validate_executor(executor):
        return {}
    d = dict(_EXECUTOR_DEFAULTS[executor])
    if model:
        d["model"] = model
    if provider:
        d["provider"] = provider
    if key_env:
        d["key_env"] = key_env
    return d


def render_executors_yaml(executors: dict) -> str:
    """把 {环节: 执行者名} 渲染成 executors.yaml 文本。非法执行者 → ValueError。"""
    lines = [
        "# executors.yaml · 4 环节执行者配置（v0.3.0 执行者选择器）",
        "# 执行者：claude(本体)/glm/deepseek/anthropic",
        "",
    ]
    for key in _KEYS:
        ex = executors.get(key)
        if not validate_executor(ex):
            raise ValueError(f"非法执行者: {ex!r}（可选 {', '.join(VALID_EXECUTORS)}）")
        entry = build_executor_entry(ex)
        lines.append(f"{key}:")
        for k, v in entry.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines) + "\n"


def save_executors(executors: dict, path: str = "") -> str:
    """按 4 环节执行者选择更新 executors.yaml。返回写出的文本。

    Args:
        executors: {rewrite: 执行者, reconcile: 执行者, quality_check: 执行者, scoring: 执行者}
        path: 输出路径；空默认 configs/executors.yaml。
    """
    text = render_executors_yaml(executors)
    if not path:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "configs", "executors.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text
