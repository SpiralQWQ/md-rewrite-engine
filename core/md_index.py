"""core/md_index.py — 课程笔记 → 总索引 index.md 的纯算法（知识点地图）。

纯函数、零外部依赖、零 IO（core 域铁律：不 import providers/services/configs）。
文件扫描与写入归集成层（orchestrator/cli），本模块只做"文本 → 索引文本"。

对应 D1：AI 看懂整门课的第一块拼图——先读 index.md 定位讲次与顺序，
再按需打开具体笔记，避免整目录倾倒（v5 经验 5：索引替代全文倾倒省 token 66%；
OKF index.md 约定 + student-llm-wiki 总目录）。
"""
from __future__ import annotations

import re

# ── 模块常量（语义化默认值，无魔法数字）──
_MAX_SUMMARY = 60                      # 一句话摘要截断长度
_INDEX_FILENAME = "index.md"           # 索引文件名（扫描时跳过自身）

# frontmatter 分隔线（--- 独立成行）
_FM_BOUNDARY = re.compile(r"^---\s*$")
# frontmatter 扁平行：key: value（含 tags: [a, b] 列表）
_FM_LINE = re.compile(r"^([A-Za-z_][\w]*)\s*:\s*(.+?)\s*$")
# 任意级 Markdown 标题
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def parse_frontmatter(text: str) -> dict:
    """提取 md 开头的 YAML frontmatter（--- 到 ---）为 dict（扁平 key: value）。

    core 域零依赖，不支持嵌套结构；`tags: [a, b]` 解析为字符串列表；
    其他值去引号去空白。无 frontmatter → {}。
    """
    if not text:
        return {}
    lines = text.splitlines()
    if not lines or not _FM_BOUNDARY.match(lines[0].strip()):
        return {}
    fm: dict = {}
    for ln in lines[1:]:
        if _FM_BOUNDARY.match(ln.strip()):
            break
        m = _FM_LINE.match(ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            items = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
            fm[key] = items
        else:
            fm[key] = val.strip("\"'")
    return fm


def _skip_frontmatter(text: str) -> str:
    """去掉开头的 frontmatter 块，返回正文。"""
    if not text:
        return ""
    lines = text.splitlines()
    if lines and _FM_BOUNDARY.match(lines[0].strip()):
        for i in range(1, len(lines)):
            if _FM_BOUNDARY.match(lines[i].strip()):
                return "\n".join(lines[i + 1:])
    return text


def first_heading(text: str) -> str:
    """取正文第一个标题文本（跳过 frontmatter）。无标题 → 空串。"""
    body = _skip_frontmatter(text)
    for ln in body.splitlines():
        m = _HEADING.match(ln.strip())
        if m:
            return m.group(1).strip()
    return ""


def summary_line(text: str) -> str:
    """取正文第一个非空非标题行作为一句话摘要（截断 ≤_MAX_SUMMARY）。

    AI 友好笔记的"一句话总结"位于标题下首行；无则返回空串。
    """
    body = _skip_frontmatter(text)
    for ln in body.splitlines():
        s = ln.strip()
        if not s or _HEADING.match(s) or s in ("---", ">"):
            continue
        return s[:_MAX_SUMMARY]
    return ""


def build_index(course_name: str, notes: list) -> str:
    """把课程名 + 笔记元数据渲染成 index.md 文本（OKF 风格）。

    Args:
        course_name: 课程名（用于标题与 frontmatter）。
        notes: 按讲次顺序排列的元数据列表，每项含：
            {"file", "title", "summary", "tags"}。

    Returns:
        index.md 全文（含 frontmatter、讲次地图、统计块）。
    """
    lines = [
        "---",
        "okf_version: v0.2",
        "type: course-index",
        f"course: {course_name}",
        f"notes: {len(notes)}",
        "---",
        "",
        f"# {course_name} · 课程索引",
        "",
        "> AI 先读本索引定位讲次与顺序，再按需打开具体笔记，勿整目录倾倒。",
        "",
        "## 讲次地图",
        "",
    ]
    for i, n in enumerate(notes, 1):
        title = (n.get("title") or n.get("file") or f"讲次{i}").strip()
        summary = (n.get("summary") or "（无摘要）").strip()
        lines.append(f"{i}. [[{n['file']}|{title}]] — {summary}")
    lines += [
        "",
        "## 统计",
        "",
        f"- 讲次总数：{len(notes)}",
        "- 链接全部指向本课程笔记，AI 按需点开。",
        "",
    ]
    return "\n".join(lines)
