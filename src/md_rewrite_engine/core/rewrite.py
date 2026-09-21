"""core/rewrite.py — AI 滚动编译的纯算法调度（边分结构边压缩上下文）。

核心思想（v4/v5 共识）：
- 逐块读原文 + 前文摘要（窗口滚动）→ 每块压缩成要点 → 摘要贯穿下一块
- AI 有权标记"边界合并"（修机械粗切的误判）

纯算法、零外部依赖：LLM 通过 `summarize_fn` 回调注入（依赖倒置），
本模块只做状态机与数据流调度，可单独单测。
"""
from __future__ import annotations

from typing import Callable

# summarize_fn 契约：summarize_fn(text, prev_summary) -> (rewritten, summary, merge_with_next)
#   text: 本块原文；prev_summary: 前文摘要
#   返回 (AI 重排后的文本, 本块摘要, 是否与下一块合并 bool)
SummarizeFn = Callable[[str, str], tuple[str, str, bool]]


def rolling_compile(chunks: list, summarize_fn: SummarizeFn,
                    initial_summary: str = "") -> list:
    """对 chunk 列表做滚动编译。

    Args:
        chunks: chunk_blocks() 输出（每项含 text/breadcrumb）。
        summarize_fn: AI 摘要+重排回调（由 services 注入，如 run_rewrite）。
        initial_summary: 初始前文摘要（可空）。

    Returns:
        list[dict]：每项 {"text", "rewritten", "summary", "breadcrumb", "merged_blocks"}。
        - text: 本编译单元原文（可能已合并相邻块）
        - rewritten: AI 重排后的文本（合并块时为拼接）
        - summary: 本单元要点（贯穿到下一单元）
        - merged_blocks: 合并了多少个原始 chunk（1=未合并）
    """
    if not chunks:
        return []
    results: list = []
    prev_summary = initial_summary
    pending = None

    for chunk in chunks:
        text = chunk.get("text", "")
        if not text or not text.strip():  # 空/纯空白块跳过
            continue
        rewritten, summary, merge = summarize_fn(text, prev_summary)
        # fn 异常返回 None → 原文/空串兜底（不崩）
        if rewritten is None:
            rewritten = text
        if summary is None:
            summary = ""
        if pending is None:
            pending = {
                "text": text,
                "rewritten": rewritten,
                "summary": summary,
                "breadcrumb": chunk.get("breadcrumb", []),
                "merged_blocks": 1,
            }
        else:
            # 前块请求合并 → 本块并入上一编译单元（原文与重排都拼接）
            pending["text"] += "\n" + text
            pending["rewritten"] += "\n" + rewritten
            pending["summary"] = summary
            pending["merged_blocks"] += 1
        prev_summary = summary
        if not merge:
            results.append(pending)
            pending = None
    if pending is not None:
        results.append(pending)
    return results
