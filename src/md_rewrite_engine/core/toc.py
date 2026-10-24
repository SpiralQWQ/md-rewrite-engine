# -*- coding: utf-8 -*-
"""core/toc.py — 篇内目录（TOC）纯算法：从标题结构自动生成，零外部依赖。

篇内目录 = 笔记开头的"本篇目录"，列出本笔记所有小节层级（GitHub 惯例：不含文档主标题）。
由脚本后处理自动生成，AI/本体无需手写——确定性机械活交代码，省 token、精确一致。
标题改过之后要刷新已有目录，走 `build_toc(text, refresh=True)`（否则目录会停在旧标题集）。

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
    """GitHub 风格锚点：小写、保留中文、逐个空格转 '-'、去标点（容错链接）。

    必须**逐个**空格替换，不能把连续空白合并成一个 '-'：删掉「知识点 2.1 · 标题」
    里的 `·` 之后，它两侧各剩一个空格，GitHub 会产出两个连字符（`21--ip`）；
    合并就会得到 `21-ip`，锚点对不上、目录点不动（回灌清单 B-8，实测 88 个链接全坏）。
    注意 `\\s` 会把制表符也算进去，GitHub 只认普通空格，所以这里用 `replace` 而不是 `re.sub`。
    """
    s = title.strip().lower()
    s = re.sub(r"[^\w一-鿿 -]", "", s)
    s = s.replace(" ", "-")
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


def strip_toc(text: str) -> str:
    """摘掉已有的篇内目录块（含它自带的那条分隔线），返回剩余全文。

    只认 render_toc 定下的形状：`## 📑 本篇目录` + 条目行（`- [标题](#锚点)`，
    可缩进）+ 收尾的 `---`。遇到**别的行**就停手——目录块跟着的引言 blockquote
    不属于它，按"下一个标题"切会把它一起吃掉（2026-10-15 实测踩过）。
    """
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip().startswith("##") and _TOC_TITLE in ln), None)
    if start is None:
        return text
    end = start + 1
    while end < len(lines):
        s = lines[end].strip()
        if s == "---":            # render_toc 固定的块尾分隔线，吃到它就收工
            end += 1
            break
        if s == "" or s.lstrip().startswith("- ["):
            end += 1
            continue
        break
    while end < len(lines) and lines[end].strip() == "":
        end += 1      # 连块尾空行一起摘，重插后能逐字节还原
    return "\n".join(lines[:start] + lines[end:])


def build_toc(text: str, refresh: bool = False) -> tuple:
    """生成篇内目录并插入 frontmatter/主标题之后。

    Args:
        text: 笔记 md 全文。
        refresh: 已有目录时是否**重建**。默认 False = 原样跳过（保持旧的幂等语义）；
            True 用于"标题改过之后要把目录刷新过来"——旧的"只插不刷新"会让目录
            停在旧标题集、锚点全部失效，而工具还报"幂等跳过"。

    Returns:
        (new_text, headings)
        - new_text: 插入（或刷新）TOC 后的全文；无标题则原样返回；已有 TOC 且
          refresh=False 则原样返回。
        - headings: 实际提取的标题列表（不含文档主标题）；空 = 未生成。
    """
    if not isinstance(text, str) or not text.strip():
        return text, []
    text = text.lstrip("﻿")   # 剥 BOM（幂等检查/插入定位都基于行首匹配，BOM 会全链失效）
    has_toc = any(ln.strip().startswith("##") and _TOC_TITLE in ln
                  for ln in text.splitlines())
    if has_toc and not refresh:
        return text, extract_headings(text)
    if has_toc:
        text = strip_toc(text)
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
