"""core/concepts.py — 核心概念聚合页的纯算法（一概念一页，跨讲累积）。

纯函数、零外部依赖、零 IO（core 域铁律）。从课程笔记提取核心概念并渲染概念页——
AI 教到该概念时读一页就全，不靠各讲碎片拼。

对应 D7（student-llm-wiki concepts/ 借鉴："跨课程连接是整个 wiki 最有价值的输出"）。
概念抽取是"机械打底"：从词汇表栏/正文的粗体英文术语提取候选，人工可增删；
文件扫描与写入归集成层（orchestrator）。
"""
from __future__ import annotations

import re

# ── 模块常量（语义化，无魔法数字）──
# 粗体英文术语：**Term**（词汇表栏/正文强调）；支持连字符/点号（state-of-the-art / HMM 2.0）
_BOLD_TERM = re.compile(r"\*\*([A-Za-z][A-Za-z0-9\-. ]{2,})\*\*")
_MAX_CTX_PER_OCC = 3     # 每篇最多摘录句数（防刷屏）
_MAX_CTX_LEN = 200       # 摘录句最大长度
_CONCEPT_TAG = "concept"  # 概念页 frontmatter type


def extract_terms(text: str) -> list:
    """从文本提取粗体英文术语（**Term**），去重保序。

    glossary 栏术语/正文强调均用 **粗体**，是核心概念候选。
    无粗体英文 → 空列表。
    """
    if not isinstance(text, str) or not text:
        return []
    seen = set()
    out = []
    for m in _BOLD_TERM.finditer(text):
        t = m.group(1).strip()
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def find_context(text: str, concept: str) -> list:
    """找含 concept（忽略大小写）的句子，作为概念页定义摘录。

    Returns:
        list[str]：含该概念的句子（≤_MAX_CTX_PER_OCC，句长 ≤_MAX_CTX_LEN 防刷屏）。
    """
    if not isinstance(text, str) or not concept:
        return []
    hits = []
    low = concept.lower()
    for ln in text.splitlines():
        s = ln.strip()
        if not s or len(s) > _MAX_CTX_LEN:
            continue
        if low in s.lower():
            hits.append(s)
            if len(hits) >= _MAX_CTX_PER_OCC:
                break
    return hits


def build_concept_page(concept: str, occurrences: list) -> str:
    """渲染概念页文本（OKF 风格：type=concept + 出现讲次 + 摘录定义）。

    Args:
        concept: 概念名。
        occurrences: [{"file": str, "contexts": [str]}] 该概念在各讲的出现。

    Returns:
        concept 页 markdown 全文。
    """
    lines = [
        "---",
        f"type: {_CONCEPT_TAG}",
        f"name: {concept}",
        "---",
        "",
        f"# {concept}",
        "",
        "## 出现讲次",
        "",
    ]
    for occ in occurrences:
        lines.append(f"- [[{occ['file']}]]")
    lines += ["", "## 摘录定义", ""]
    for occ in occurrences:
        for ctx in occ.get("contexts", []):
            lines.append(f"- `{ctx}`")
    lines += ["", "> 概念页由机械抽取打底，可人工完善定义与概念关系。", ""]
    return "\n".join(lines)
