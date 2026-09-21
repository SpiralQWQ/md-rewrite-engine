"""core/search.py — 极简词法检索（D8，零依赖，不引向量库）。

纯函数、零外部依赖、零 IO。对课程笔记做关键词搜索——AI 能"找"知识点而非"全读"
（OKFy 确定性词法检索 search_concepts 借鉴；先不引向量库，量大再评估 SQLite FTS5）。

输入 {file: content}，query 拆词，返回命中笔记 + 定位段落，按命中数降序。
"""
from __future__ import annotations

import re

# 词拆分：空白 + 中英文标点
_WORD_SPLIT = re.compile(r"[\s,，。;；:：、.!！?？\"'“”‘’()（）\[\]【】《》<>]+")
_MAX_HITS_PER_FILE = 3    # 每篇最多返回命中段落数
_MAX_HIT_LEN = 120        # 命中段采样截断


def split_query(query: str) -> list:
    """把查询拆成词（空白/标点分隔），去空去重。"""
    if not isinstance(query, str) or not query.strip():
        return []
    seen = set()
    out = []
    for w in _WORD_SPLIT.split(query.lower()):
        w = w.strip()
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def search(texts: dict, query: str, top_k: int = 5) -> list:
    """在 {file: content} 中做词法检索。

    Args:
        texts: {文件名: 全文}。
        query: 关键词查询。
        top_k: 返回最多笔记数。

    Returns:
        list[dict]：{"file", "score", "hits"}，按 score 降序。
        - score: 命中词次数（同一段多词命中累加）
        - hits: 含关键词的段落（≤_MAX_HITS_PER_FILE，≤_MAX_HIT_LEN）
    """
    if not isinstance(texts, dict) or not texts:
        return []
    words = split_query(query)
    if not words:
        return []
    results = []
    for file, content in texts.items():
        if not isinstance(content, str):
            continue
        hits = []
        score = 0
        for ln in content.splitlines():
            s = ln.strip()
            if not s:
                continue
            low = s.lower()
            matched = [w for w in words if w in low]
            if matched:
                score += len(matched)
                if len(hits) < _MAX_HITS_PER_FILE:
                    hits.append(s[:_MAX_HIT_LEN])
        if hits:
            results.append({"file": file, "score": score, "hits": hits})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max(1, top_k)]
