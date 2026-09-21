"""core/chunk.py — Block 列表 → 切块（防超限 + 块间重叠）。

纯算法、零外部依赖。在 assemble（标题树）基础上，按 max_chars 把内容切成
适合 AI 滚动编译的 chunk：每块带面包屑，块间保留 overlap 尾部（防切半句）。

注意：max_chars 用"字符数"近似 token（中文教学，1 字 ≈ 1 token，偏保守）。
"""
from __future__ import annotations

from md_rewrite_engine.core.assemble import Block

# ── 默认参数（可由调用方覆盖；非魔法数字，是语义化默认值）──
_MAX_CHARS_DEFAULT = 8000      # 每块最大字符（AI 一次处理窗口）
_OVERLAP_DEFAULT = 200         # 块间重叠字符（防切半句）


def render_block(b: Block) -> str:
    """把 Block 渲染成可切文本：'# 完整标题\\n正文'。

    标题用 full_title（含父标题面包屑），保证切块后 AI 也知道上下文。
    """
    if b is None:
        return ""
    if not b.title:
        return b.text
    head = f"# {b.full_title}"
    parts = [p for p in (head, b.text) if p]
    return "\n".join(parts)


def _group_paragraphs(lines: list) -> list:
    """把行列表按空行分组成段落（段落边界 = 空行）。

    A2 段落边界切的核心：空行是语义边界，段落内的行保持完整，AI 读到连贯语义。
    空行/纯空白行视为分隔符；无空行时整组为一段。
    """
    paragraphs: list = []
    cur: list = []
    for ln in lines:
        if ln.strip():
            cur.append(ln)
        else:
            if cur:
                paragraphs.append(cur)
                cur = []
    if cur:
        paragraphs.append(cur)
    return paragraphs


def _para_join(paras: list) -> str:
    """把段落列表拼成文本：段内行用换行、段落间用空行（保留段落边界）。"""
    return "\n\n".join("\n".join(p) for p in paras)


def _split_long_para(para: list, max_chars: int) -> list:
    """把超长段落按行/字符硬切成多段（每段 ≤ max_chars）。

    仅当单个段落超长（>max_chars，罕见）才走这里兜底——段落本身无法再按空行切。
    单行超长按字符硬切；AI 靠块间重叠拼回上下文。
    """
    max_chars = max(1, max_chars)  # 防死循环（0/负数会使硬切不推进）
    out, buf, buf_len = [], [], 0
    for ln in para:
        # 单行超长（>max_chars，罕见）：按字符硬切，防整块超限；AI 靠块间重叠拼回上下文
        while len(ln) > max_chars:
            if buf:
                out.append("\n".join(buf))
                buf, buf_len = [], 0
            out.append(ln[:max_chars])
            ln = ln[max_chars:]
        if buf and buf_len + len(ln) > max_chars:
            out.append("\n".join(buf))
            buf, buf_len = [], 0
        buf.append(ln)
        buf_len += len(ln)
    if buf:
        out.append("\n".join(buf))
    return out


def _split_lines_by_chars(lines: list, max_chars: int) -> list:
    """把行列表切成多个小段：优先按空行段落边界切，单段超长才字符硬切兜底。

    A2 段落边界切（治"无标题 md 乱切"）：无标题流水账按空行分块，每块是完整段落，
    AI 读到连贯语义、不切半句；仅当单个段落本身超长（>max_chars，罕见）才按字符
    硬切兜底防超限。
    """
    max_chars = max(1, max_chars)  # 防死循环（0/负数会使硬切不推进）
    out: list = []
    buf: list = []       # 当前块的段落（list[段落 = list[行]]）
    buf_len = 0
    for para in _group_paragraphs(lines):
        para_len = sum(len(ln) for ln in para)
        # 单段超长（>max_chars，罕见）：先封当前块，再按字符硬切该段
        if para_len > max_chars:
            if buf:
                out.append(_para_join(buf))
                buf, buf_len = [], 0
            out.extend(_split_long_para(para, max_chars))
            continue
        # 当前块装得下 → 并入；装不下 → 封块，该段从新块开始（段落边界切）
        if buf and buf_len + para_len > max_chars:
            out.append(_para_join(buf))
            buf, buf_len = [], 0
        buf.append(para)
        buf_len += para_len
    if buf:
        out.append(_para_join(buf))
    return out


def chunk_blocks(blocks: list, max_chars: int = _MAX_CHARS_DEFAULT,
                 overlap_chars: int = _OVERLAP_DEFAULT) -> list:
    """把 Block 列表切成 chunk。

    Args:
        blocks: assemble() 输出的 Block 列表。
        max_chars: 每块最大字符数。
        overlap_chars: 相邻块间保留的尾部重叠字符数（防切半句）。

    Returns:
        list[dict]：每项 {"text", "breadcrumb", "overlap"}。
        - text: 本块文本（含标题；若 overlap=True，开头是前块尾部重叠段）
        - breadcrumb: 本块最后 Block 的面包屑
        - overlap: 本块是否以"前块尾部重叠段"开头
    """
    if not blocks:
        return []
    max_chars = max(1, max_chars)          # 防 0/负数导致死循环
    overlap_chars = max(0, overlap_chars)  # 防负数导致 text[-负数:] 行为异常
    chunks: list = []
    cur: list = []
    cur_len = 0
    cur_bc: list = []
    overlap_flag = False  # 当前块是否以"前块尾部重叠段"开头

    def seal() -> None:
        """封当前块（不附加重叠段）。"""
        nonlocal cur, cur_len, overlap_flag
        text = "\n".join(cur)
        chunks.append({"text": text, "breadcrumb": cur_bc, "overlap": overlap_flag})
        cur, cur_len, overlap_flag = [], 0, False

    for b in blocks:
        bt = render_block(b)
        if not bt:
            continue
        cur_bc = b.breadcrumb
        # 已有内容 + 再加会超限 → 封块；新块开头带前块尾部重叠（防切半句）
        if cur and cur_len + len(bt) > max_chars:
            text = "\n".join(cur)
            tail = text[-overlap_chars:] if len(text) > overlap_chars else text
            seal()
            if tail:
                cur.append(tail)
                cur_len = len(tail)
                overlap_flag = True
        if len(bt) > max_chars:
            # 单块超限：清空当前，按行拆；片段标 overlap（AI 注意衔接，含硬切段）
            if cur:
                seal()
            lines = bt.splitlines()
            for piece in _split_lines_by_chars(lines, max_chars):
                chunks.append({"text": piece, "breadcrumb": b.breadcrumb, "overlap": True})
            cur, cur_len, overlap_flag = [], 0, False
        else:
            cur.append(bt)
            cur_len += len(bt)
    if cur:
        seal()
    return chunks
