# -*- coding: utf-8 -*-
"""core/toc.py — 篇内目录（TOC）纯算法：从标题结构自动生成，零外部依赖。

篇内目录 = 笔记开头的"本篇目录"，列出本笔记所有小节层级（GitHub 惯例：不含文档主标题）。
由脚本后处理自动生成（幂等），AI/本体无需手写——确定性机械活交代码，省 token、精确一致。

依赖方向：core 零外部依赖（只 import re 标准库）；orchestrator 调 build_toc 做后处理。
"""
from __future__ import annotations

import re

_TOC_TITLE = "📑 本篇目录"
_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


def parse_frontmatter_end(text: str) -> int:
    """返回 frontmatter 结束后的行号（0 = 无 frontmatter）。

    先剥 BOM（\\ufeff）：PowerShell/Set-Content 写盘默认带 BOM，贴在首个 `---`
    前会让 frontmatter 判定失败、TOC 错插到文件最开头（2026-09-20 实测第8/10/11章）。
    """
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
    return 0


def extract_headings(text: str) -> list:
    """提取正文标题 [(level, title), ...]，跳过 frontmatter / 代码块 / 已有 TOC 块。

    标题层级从 H1-H4（更深层级不进 TOC，防过度嵌套）。返回空列表 = 无标题。
    """
    lines = text.splitlines()
    start = parse_frontmatter_end(text)
    headings = []
    in_code = False
    in_toc = False
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if in_toc:
            if s and s.startswith("#") and _TOC_TITLE not in s:
                in_toc = False
            else:
                continue
        if _TOC_TITLE in s:
            in_toc = True
            continue
        m = _HEADING.match(s)
        if m:
            headings.append((len(m.group(1)), m.group(2).strip()))
    return headings


def _slug(title: str) -> str:
    """GitHub 风格锚点：小写、保留中文、空格转 '-'、去标点（容错链接）。"""
    s = title.strip().lower()
    s = re.sub(r"[^\w一-鿿 -]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def render_toc(headings: list) -> str:
    """渲染 TOC 块文本：缩进按标题层级（最小层级为基准），带锚点链接。

    Args:
        headings: [(level, title), ...]（应已排除文档主标题）。

    Returns:
        str TOC 块（含前后空行）；无标题返回 ""。
    """
    if not headings:
        return ""
    base = min(lv for lv, _ in headings)
    lines = [f"## {_TOC_TITLE}", ""]
    for lv, title in headings:
        indent = "  " * (lv - base)
        lines.append(f"{indent}- [{title}](#{_slug(title)})")
    lines += ["", "---", ""]
    return "\n".join(lines)


def build_toc(text: str) -> tuple:
    """生成篇内目录并插入 frontmatter/主标题之后（幂等：已有 TOC 则原样跳过）。

    Args:
        text: 笔记 md 全文。

    Returns:
        (new_text, headings)
        - new_text: 插入 TOC 后的全文（无标题则原样返回；已有 TOC 则原样返回）。
        - headings: 实际提取的标题列表（不含文档主标题）；空 = 未生成。
    """
    if not isinstance(text, str) or not text.strip():
        return text, []
    text = text.lstrip("﻿")   # 剥 BOM（幂等检查/插入定位都基于行首匹配，BOM 会全链失效）
    # 幂等：已有篇内目录 → 原样跳过（不重复插入、不重写，防空行漂移）
    for ln in text.splitlines():
        if ln.strip().startswith("##") and _TOC_TITLE in ln:
            return text, extract_headings(text)
    headings = extract_headings(text)
    # 跳过文档主标题（第一个 H1），TOC 从二级标题开始（GitHub 惯例）
    if headings and headings[0][0] == 1:
        headings = headings[1:]
    toc = render_toc(headings)
    if not toc:
        return text, []
    lines = text.splitlines()
    start = parse_frontmatter_end(text)
    # 插入位置：frontmatter 后；若正文首行是文档主标题(H1)，TOC 插在它后面
    insert_at = start
    body_start = start
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    if body_start < len(lines) and re.match(r"^#\s+", lines[body_start].strip()):
        insert_at = body_start + 1
    new_lines = lines[:insert_at] + [toc] + lines[insert_at:]
    return "\n".join(new_lines), headings
