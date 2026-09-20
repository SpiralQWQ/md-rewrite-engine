"""core/assemble.py — 清洗后 md → 内部结构（标题树/面包屑）。

纯算法、零外部依赖（目录契约铁律：core 不 import providers/services/configs）。
把清洗后 md 解析成带层级的 Block 列表，每块带父标题面包屑，
供下游 chunk（切块）和 rewrite（滚动编译）使用。

无 # 标记的标题靠模式识别（v4 实测教训：不靠 # 也能认标题）。

定位（A3）：assemble 是"粗切打底"——只做能确定的标题识别；无标题 md（纯流水账）
返回 1 个根块（不建假树、不崩），下游 chunk 按段落边界切、AI 滚动补结构才是主角。
空行作为段落边界保留到当前块（A2 段落切依赖，丢了解析层就没段落信息）。
"""
import re

# ── 模块常量（无魔法数字 / 无硬编码路径）──

# # 标记标题：'# 标题' / '## 二级' → (level, title)
_HASH_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 无标记序号式标题：'第1章 绪论' / '第X讲 xxx'
_ORD_HEADING = re.compile(r"^第[一二三四五六七八九十百0-9]+\s*[章讲节篇课部分]")
# 注：不自动识别"1.2 xxx"纯数字小节——3.14/年份/版本号无法可靠区分（v5 实测教训：
#   规则宁漏勿误）。数字小节交给下游 AI 滚动编译兜底（AI 能理解它是小节标题）。
# 白名单标题词（独立成行整行匹配即标题）：源自 text-cleaning-engine 教学标题词
_WORD_HEADINGS = frozenset({
    "绪论", "引言", "概述", "小结", "总结", "结语", "结论",
    "复习", "练习", "习题", "作业", "思考题", "案例", "举例", "例题",
    "定义", "原理", "概念", "特点", "分类", "作用", "意义", "目标",
    "重点", "难点", "拓展", "延伸", "参考资料", "学习目标", "随堂测验",
    "课后作业", "实战演练", "知识拓展", "温馨提示", "注意事项",
    "常见问题", "易错点", "预习", "导入", "导学",
})
# 无标记标题最大长度（超过就当正文，防误判长句）
_MAX_NOMARK_LEN = 30


class Block:
    """一个内容块：标题层级 + 标题 + 内容行 + 父标题面包屑。"""

    __slots__ = ("level", "title", "lines", "breadcrumb")

    def __init__(self, level: int, title: str, breadcrumb: list) -> None:
        self.level = level
        self.title = title
        self.lines = []          # 本块正文行（不含标题行）
        self.breadcrumb = breadcrumb  # 父标题链，如 ['第1讲', '1.1 定义']

    @property
    def text(self) -> str:
        """本块正文（不含面包屑，供下游 chunk/rewrite 用）。"""
        return "\n".join(self.lines).strip()

    @property
    def full_title(self) -> str:
        """带面包屑的完整路径标题，如 '第1讲 > 1.1 定义'。"""
        return " > ".join([*self.breadcrumb[:-1], self.title]) if self.title else " > ".join(self.breadcrumb)


def detect_heading(line: str):
    """识别一行是否为标题。

    Args:
        line: 单行文本（未 strip 亦可）。

    Returns:
        (level:int, title:str) 是标题；None 不是标题。
    """
    if line is None or not isinstance(line, str):
        return None
    m = _HASH_HEADING.match(line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    s = line.strip()
    if not s or len(s) > _MAX_NOMARK_LEN:
        return None
    if _ORD_HEADING.match(s) or s in _WORD_HEADINGS:
        return 2, s
    return None


def assemble(md_text: str) -> list:
    """把清洗后 md 解析成 Block 列表（含面包屑）。

    Args:
        md_text: 清洗后 md 全文（可为空）。

    Returns:
        list[Block]：标题层级正确、面包屑完整。
        空输入返回 []；无标题的正文归入一个根 Block(level=1, title='')。
    """
    if not isinstance(md_text, str):  # None / 非 str 输入 → 无内容（不崩）
        return []
    if not md_text:
        return []
    if not md_text.strip():  # 纯空白输入 → 无内容
        return []
    lines = md_text.splitlines()
    # YAML frontmatter：文档开头 `---` 到 `---` 是元数据，跳过（非正文非标题）
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break
    blocks: list = []
    stack: list = []  # 当前标题链 [(level, title), ...]
    cur: Block | None = None
    in_code = False  # 代码块围栏内不判标题（原样保留）
    in_comment = False  # HTML 注释块内不判标题
    in_math = False  # $$ 数学公式块内不判标题

    for line in lines:
        # $$ 数学公式块（行首 $$ 切换；公式内 # 不判标题，同代码块）
        if line.strip().startswith("$$"):
            in_math = not in_math
            if cur is None:
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
            continue
        if in_math:
            if cur is None:
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
            continue
        # 代码块围栏（``` / ```python）切换状态；围栏及内部行一律当正文，不判标题
        if line.strip().startswith("```"):
            in_code = not in_code
            if cur is None:
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
            continue
        if in_code:
            if cur is None:
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
            continue
        # HTML 注释块（<!-- ... -->）：块内 # 不判标题（防误判，同代码块）
        if in_comment:
            if cur is None:
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
            if "-->" in line:
                in_comment = False
            continue
        if line.strip().startswith("<!--"):
            in_comment = True
            if cur is None:
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
            if "-->" in line:  # 单行注释
                in_comment = False
            continue
        h = detect_heading(line)
        if h:
            level, title = h
            # 维护标题栈：弹出比当前更深/同级的祖先，保证面包屑正确
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            breadcrumb = [t for _, t in stack]
            cur = Block(level, title, breadcrumb)
            blocks.append(cur)
        else:
            if not line.strip():
                # 空行：不创建根块；但作为"段落边界"保留到当前块（A2 段落切依赖，
                # 下游 chunk 按空行识别段落边界，丢了就变字符硬切）
                if cur is not None:
                    cur.lines.append(line)
                continue
            if cur is None:
                # 正文出现在第一个标题前 → 根块（标题空）
                cur = Block(1, "", [])
                blocks.append(cur)
            cur.lines.append(line)
    return blocks
