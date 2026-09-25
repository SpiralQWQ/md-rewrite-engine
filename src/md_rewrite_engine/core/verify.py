"""core/verify.py — 语义对账 + 质量评分（纯算法兜底，锁"准确稳定"）。

原理（v4 实测：完整性靠机械对账，不靠 AI 自说自话）：
- reconcile：从原文提取"关键信息点"（英文术语/数字/中英长词），检查重排后是否仍出现，
  覆盖率低于阈值即报缺失——这是"内容丢没丢"的机械兜底
- score：对重排结果做可计算质量评分（保留率/结构/噪音）
- check：组合入口，返回是否通过阈值 + 问题清单

真正的语义级对账/矛盾检测靠 LLM（services/llm.py）；本模块做确定性兜底。
纯算法、零外部依赖。
"""
from __future__ import annotations

import re

# ── 默认参数（语义化默认值，可由调用方覆盖）──
_KEYWORD_MIN_LEN = 2            # 中文关键短语最小长度（保留，中文提取逻辑已交语义对账）
_EN_WORD_MIN_LEN = 3            # 英文单词最小长度（过滤短词/单字母）
_NUM_MIN = 1                    # 数字保留检测（单数字由 _DIGIT_MIN_LEN 过滤）
_DIGIT_MIN_LEN = 2              # 数字有效位最小长度（滤 ASR 单数字噪声：3000→"300 0"的"0"）
_COVERAGE_THRESHOLD = 0.9       # 关键信息点覆盖率阈值（<90% 报缺失）
_SCORE_THRESHOLD = 80           # 质量分及格线

# 关键信息点提取
_TOKEN_SPLIT = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?|[一-鿿]{2,}")

# 术语变体检测最小窗口（>=4 字：3 字窗口全是虚词碎片误报；2 字段=常用词互转）
_VARIANT_MIN_LEN = 4
# 虚词前导表（窗口以这些字开头 = 量词/虚词碎片，实测全是措辞差异非错字；
# 真术语窗口以实词开头：文件型/轻量级/各种数据库）
_VARIANT_STOP_HEADS = frozenset("的到是了在有和与或等各每把将从被以于其中这那及就不也")


def extract_keypoints(text: str) -> set:
    """提取"事实关键点"：英文术语(≥3) + 数字(≥2 有效位，含版本号如 3.12)。

    不提取中文——中文概念（含口语/ASR 错听/重排重组）由 AI 语义对账
    （semantic_reconcile）兜底。原因：重排会纠正 ASR 错听（mic→Mac）、
    给句子加标点、重组中文表达，若把中文/英文 token 当"必留关键点"精确比对，
    必然大量误报（实测 11.9% 死锁）。数字是重排必须原样保留的硬事实，才适合
    机械精确核查。core 零依赖铁律不变。
    """
    if not text:
        return set()
    pts = set()
    for tok in _TOKEN_SPLIT.findall(text):
        if tok.isalpha() and tok.isascii():
            if len(tok) >= _EN_WORD_MIN_LEN:
                pts.add(tok.lower())
        elif tok.isdigit() or "." in tok:
            num = tok.replace(".", "")
            if len(num) >= 10:              # 超长纯数字 = 视频ID/哈希（非教学内容），跳过防机械对账误报
                continue
            if len(num) >= _DIGIT_MIN_LEN:
                pts.add(tok)
    return pts


def _digit_covered(tok: str, dst_digits: set) -> bool:
    """数字合并匹配：tok 在重排数字中，或是某重排数字的子串（ASR 拆散 300 0 → 3000）。"""
    if tok in dst_digits:
        return True
    return any(tok in nd for nd in dst_digits)


def reconcile(original: str, rewritten: str) -> dict:
    """机械对账（轻量事实核查）：数字硬判定 + 英文软提示，中文交 AI 语义对账。

    关键点 = 数字(≥2 位) + 英文(≥3)。ASR 转写/重排场景下，英文会被纠正（错听 mic→Mac）
    或改写，若硬判必误报 → 英文缺失降级为 warnings 提示；只有数字是"重排必须原样保留"
    的硬事实，其覆盖率 ≥90% 才算通过。中文概念缺失由 services 层 semantic_reconcile（AI）兜底。

    Returns:
        {"missing", "coverage", "total", "ok", "warnings"}
        - missing: 缺失的数字（硬缺失，≤10 防刷屏）
        - coverage: 数字覆盖率 0~1
        - ok: 数字覆盖率 ≥ _COVERAGE_THRESHOLD
        - warnings: 缺失的英文术语（软提示，≤10；不判 ok）
    """
    src = extract_keypoints(original)
    dst = extract_keypoints(rewritten)
    if not src:
        return {"missing": [], "coverage": 1.0, "total": 0, "ok": True, "warnings": []}
    src_digit = {t for t in src if t.isdigit() or "." in t}
    src_en = {t for t in src if t.isalpha() and t.isascii()}
    dst_digit = {t for t in dst if t.isdigit() or "." in t}
    if src_digit:
        missing = sorted(t for t in src_digit if not _digit_covered(t, dst_digit))
        coverage = 1.0 - len(missing) / len(src_digit)
        ok = coverage >= _COVERAGE_THRESHOLD
    else:
        missing, coverage, ok = [], 1.0, True
    warnings = sorted(t for t in src_en if t not in dst)[:10]
    return {
        "missing": missing[:10],
        "coverage": round(coverage, 3),
        "total": len(src_digit),
        "ok": ok,
        "warnings": warnings,
    }


def score(rewritten: str, original: str = "") -> dict:
    """质量评分（可计算指标，0-100）。None/非 str 输入 → 0 分（不崩）。"""
    rewritten = rewritten if isinstance(rewritten, str) else ""
    original = original if isinstance(original, str) else ""
    if not rewritten.strip():
        return {"score": 0, "detail": {"empty": True}}
    lines = [l for l in rewritten.splitlines() if l.strip()]
    has_heading = any(re.match(r"^#{1,6}\s", l) for l in lines)
    n_lines = len(lines)
    # 长度合理：>5 行且平均行不空壳
    len_ok = n_lines >= 5
    # 噪音：连续重复空行（已过滤空行）；纯符号短行
    noise = sum(1 for l in lines if len(l) <= 1 and not re.search(r"[一-鿿A-Za-z0-9]", l))
    s = 40.0                          # 基础分
    if has_heading:
        s += 20                        # 结构分
    if len_ok:
        s += 20                        # 长度分
    s += 20 if noise == 0 else 10     # 噪音分
    if original:
        r = reconcile(original, rewritten)
        s += (r["coverage"] - 0.9) * 100  # 保留率加成
    s = max(0.0, min(100.0, round(s, 1)))
    return {"score": s, "detail": {"has_heading": has_heading, "lines": n_lines, "noise": noise}}


def check(original: str, rewritten: str,
          score_threshold: int = _SCORE_THRESHOLD) -> dict:
    """组合入口：对账 + 评分 → 是否通过。None 输入 → 不过（不崩）。"""
    original = original if isinstance(original, str) else ""
    rewritten = rewritten if isinstance(rewritten, str) else ""
    issues = []
    r = reconcile(original, rewritten)
    if not r["ok"]:
        issues.append(f"内容缺失 {len(r['missing'])} 个关键点（覆盖率 {r['coverage']:.0%}）：{', '.join(r['missing'][:5])}")
    sc = score(rewritten, original)
    if sc["score"] < score_threshold:
        issues.append(f"质量分 {sc['score']} < 阈值 {score_threshold}")
    if not rewritten.strip():
        issues.append("输出为空")
    return {"pass": not issues, "score": sc["score"], "issues": issues,
            "warnings": r.get("warnings", [])}


# ── D2 链接校验（v1.3 互链规范）──
# 匹配 [[目标#锚点|显示文本]] / [[目标|显示]] / [[目标]]，捕获目标
_LINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def extract_links(text: str) -> list:
    """提取文本中所有 [[链接]] 的目标（不含 # 锚点 / | 显示文本）。"""
    if not isinstance(text, str) or not text:
        return []
    return [m.group(1).strip() for m in _LINK_PATTERN.finditer(text)]


def validate_links(text: str, known_targets: set = None) -> dict:
    """校验 [[链接]] 目标是否都在已知目标集合内。

    D2 约定（OKFy）：缺目标标 warning 不报错——不阻断主流程，但列出悬空链接
    供人工抽查。无 known_targets（None/空）时无法校验 → 视为通过（不误报）。

    Args:
        text: 含 [[链接]] 的文本。
        known_targets: 课程内已知目标集合（文件名/讲次标识）；None/空 → 跳过校验。

    Returns:
        {"links": int, "broken": list, "ok": bool}
        - links: 链接总数
        - broken: 悬空链接目标（≤10 防刷屏）
        - ok: 无悬空链接
    """
    if not isinstance(text, str):
        return {"links": 0, "broken": [], "ok": True}
    links = extract_links(text)
    if not known_targets:
        return {"links": len(links), "broken": [], "ok": True}
    broken = [t for t in links if t not in known_targets]
    return {"links": len(links), "broken": broken[:10], "ok": not broken}


# ── D3 关联字段校验（v1.3）──
_RELATION_FIELDS = ("prerequisites", "next", "related")

def validate_relations(frontmatter: dict, known_targets: set = None) -> dict:
    """校验 frontmatter 关联字段（prerequisites/next/related）。

    D3 约定：字段非空且指向存在（与 known_targets 比对，去 #锚点、容错带/不带扩展）；
    缺字段/空/悬空 → warning 不阻断（供抽查）。无 known → 只校验缺失与空值。

    Args:
        frontmatter: 笔记 frontmatter dict。
        known_targets: 课程内已知目标集合；None/空 → 只校验非空。

    Returns:
        {"ok", "missing": list, "broken": list}
        - missing: 缺失或为空的字段名
        - broken: 指向不存在目标的 "字段=值"
    """
    missing = []
    broken = []
    if not isinstance(frontmatter, dict):
        return {"ok": True, "missing": [], "broken": []}
    for field in _RELATION_FIELDS:
        val = frontmatter.get(field)
        if not val:
            missing.append(field)
            continue
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            s = str(v).strip()
            if not s:
                missing.append(field)
                continue
            target = s.split("#")[0].strip()  # 去锚点：01_第1讲.md#变量 → 01_第1讲.md
            if known_targets and target not in known_targets:
                broken.append(f"{field}={s}")
    return {"ok": not broken, "missing": missing, "broken": broken}


# ── D4 条目级引用抽查（v1.3）──
_SOURCE_MARK = re.compile(r"[（(]来源[:：]")   # 出处标记 (来源: / （来源：
_SRC_SAMPLE_LEN = 40                            # 缺出处行采样截断长度


def find_missing_source(text: str) -> list:
    """扫描"示例/原句"栏，找出缺条目级出处的行（D4 抽查辅助）。

    近似规则（只做机械统计供人工抽查，不阻断）：含"示例/原句/例如"的行，
    若行内无 `(来源: ...)` 标记 → 视为缺出处。

    Returns:
        list[str]：疑似缺出处行（≤10，防刷屏）。
    """
    if not isinstance(text, str) or not text:
        return []
    hits = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if any(kw in s for kw in ("示例", "原句", "例如")):
            if not _SOURCE_MARK.search(s):
                hits.append(s[:_SRC_SAMPLE_LEN])
    return hits[:10]


# ── D6 置信度落值校验（v1.3）──
_CONF_LEVELS = {"high", "medium", "low"}
_VERIFY_STATES = {"unverified", "machine_confirmed", "human_reviewed"}


def validate_confidence(frontmatter: dict) -> dict:
    """校验 frontmatter confidence 已实际填写（D6，不再空字段）。

    D6 约定：confidence 必须非空且在 high/medium/low 内；verified 可选，若填须在
    unverified/machine_confirmed/human_reviewed 内。缺/非法 → warning 不阻断。

    Returns:
        {"ok", "issues": list}
    """
    if not isinstance(frontmatter, dict):
        return {"ok": True, "issues": []}
    issues = []
    conf = frontmatter.get("confidence")
    if not conf:
        issues.append("confidence 缺失")
    elif str(conf).strip().lower() not in _CONF_LEVELS:
        issues.append(f"confidence 非法: {conf}")
    verified = frontmatter.get("verified")
    if verified and str(verified).strip().lower() not in _VERIFY_STATES:
        issues.append(f"verified 非法: {verified}")
    return {"ok": not issues, "issues": issues}


# ── B2 语义级对账接口（概念覆盖，非词级）──
def semantic_reconcile(original, rewritten, call=None) -> dict:
    """语义级对账（B2）：调 LLM 判断"概念是否覆盖"，非词级数关键词。

    core 零依赖铁律：LLM 通过 call 回调注入（services 层绑定 prompt + 模型）。
    能检出"词级对账漏掉但概念级缺失"的 case（如 STAR法则 被改写为 四段式描述）。
    LLM 不可用/异常 → 降级返回空缺失（不阻断主流程）。

    Args:
        original: 原文。
        rewritten: 重排后。
        call: 语义对账回调 call(original, rewritten) -> list[str] 缺失概念。

    Returns:
        {"missing": list, "ok": bool}
    """
    if call is None:
        return {"missing": [], "ok": True}
    try:
        missing = call(original, rewritten)
        missing = [str(x) for x in missing if str(x).strip()] if isinstance(missing, list) else []
        return {"missing": missing, "ok": not missing}
    except Exception:  # noqa: BLE001 LLM 失败降级，不阻断
        return {"missing": [], "ok": True}


# ── C3d 轻量 frontmatter schema 校验（不引 jsonschema，core 零依赖）──
def validate_frontmatter_schema(frontmatter: dict, required: list, types: dict = None) -> dict:
    """校验 frontmatter 必填字段存在 + 类型（C3d 轻量 schema）。

    core 零依赖铁律：不用 jsonschema 库，纯 Python 实现必填/类型校验。

    Args:
        frontmatter: 笔记 frontmatter dict。
        required: 必填字段列表（缺/空 → missing）。
        types: {field: expected_type}，如 {"tags": list, "title": str}。

    Returns:
        {"ok", "missing": list, "type_errors": list}
    """
    missing = []
    type_errors = []
    if not isinstance(frontmatter, dict):
        return {"ok": False, "missing": list(required), "type_errors": []}
    for f in required:
        if f not in frontmatter or frontmatter[f] in (None, ""):
            missing.append(f)
    for f, t in (types or {}).items():
        if f in frontmatter and frontmatter[f] not in (None, ""):
            if t == list and not isinstance(frontmatter[f], list):
                type_errors.append(f"{f} 应为列表")
            elif t == str and not isinstance(frontmatter[f], str):
                type_errors.append(f"{f} 应为字符串")
    return {"ok": not missing and not type_errors, "missing": missing, "type_errors": type_errors}


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein 编辑距离（动态规划，标准实现；输入保证为短中文词）。"""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return max(la, lb)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def term_variants(original: str, rewritten: str) -> list:
    """中文术语近形变体检测（错别字机检，纯算法兜底）。

    原理：两侧各抽连续中文段（_TOKEN_SPLIT 的 [一-鿿]{2,} token），对 **≥3 字段**
    找**等长且编辑距离=1** 的对应段——即"术语中替换了 1 个字"形态。实测调优
    （14 章真实重排 3 轮迭代）：① 不等长改写全部放过（合法改写=虚词增删：
    加"的"、删"中"、并句）；② 2 字段等长替换不报（常用词互转太泛：通常→通过、
    首先→要先，实测 119 条全是改写非错字）；③ ≥3 字段等长换 1 字只剩两类——
    同音/形近错字（调度器→掉度器）与真语义替换（子节点→父节点），两者都值得
    人工复核，实测每章 0~10 条、无误伤拦截（软提示不判 pass）。

    Returns:
        [{"term": 原文段, "variant": 重排版近形段, "distance": int}]，≤10 条防刷屏。
    """
    if not isinstance(original, str) or not isinstance(rewritten, str):
        return []
    if not original or not rewritten:
        return []
    src_segs = [t for t in _TOKEN_SPLIT.findall(original)
                if len(t) >= _VARIANT_MIN_LEN and not t.isascii()]
    dst_segs = [t for t in _TOKEN_SPLIT.findall(rewritten)
                if len(t) >= _VARIANT_MIN_LEN and not t.isascii()]
    if not src_segs or not dst_segs:
        return []
    dst_by_len: dict = {}
    for v in dst_segs:
        dst_by_len.setdefault(len(v), set()).add(v)
    out = []
    seen = set()
    for term in src_segs:
        if term in seen:
            continue
        seen.add(term)
        hit = None
        # 对源段的每个 n-gram 窗口（n=候选段长）找 dist≤1 的对应——
        # 整段边界在重排中会漂移（前缀词增删），等长约束只能在**窗口级**成立。
        # 窗口长度同样受 _VARIANT_MIN_LEN 约束（短窗口全是虚词碎片误报），
        # 且**最长窗口优先**——术语级替换窗口长（≥4），优先报最具体的证据。
        # 虚词前导过滤仅对「切出的子窗口」生效——整段窗口（n==len(term)）不跳：
        # 整段就是 token 本体（如"的调度器管理请求队列"），虚词开头不代表它是碎片
        for n in sorted((n for n in dst_by_len if n >= _VARIANT_MIN_LEN and n <= len(term)),
                        reverse=True):
            cands = dst_by_len[n]
            for i in range(len(term) - n + 1):
                window = term[i:i + n]
                if n < len(term) and window[0] in _VARIANT_STOP_HEADS:
                    continue                    # 虚词前导子窗口（量词/措辞碎片），非术语
                if window in cands:
                    break                       # 该窗口原样保留，无嫌疑
                for v in cands:
                    if window in v or v in window:
                        continue                # 包含关系=截断/扩展，非错字
                    if 0 < _edit_distance(window, v) <= 1:
                        hit = {"term": window, "variant": v, "distance": 1}
                        break
            if hit:
                break
        if hit:
            out.append(hit)
    return out[:10]


# ── 丰富度门禁（v0.4.5）──
# markdown 标记符号（膨胀率口径中剔除，防格式噪声干扰内容量度量）
_MD_MARKS = re.compile(r"[#*`|>\-\[\]()]")


def _content_len(text: str) -> int:
    """内容字符数：剥 frontmatter / markdown 标记 / 空白后的净内容量。

    膨胀率的度量口径——比 len(text) 抗格式噪声（md 符号多少不代表内容多少）。
    """
    if not isinstance(text, str) or not text:
        return 0
    if text.startswith("---"):
        m = re.search(r"^---\n.*?\n---\n", text, re.S)
        if m:
            text = text[m.end():]
    return len(re.sub(r"\s", "", _MD_MARKS.sub("", text)))


def expansion_ratio(original: str, rewritten: str) -> float:
    """膨胀率 = 笔记内容量 / 源内容量（丰富度门禁的核心度量，v0.4.5）。

    背景：机械对账管"丢没丢"（数字覆盖率），管不了"讲不讲得开"——一篇对账
    100% 的笔记照样可以把完整推导压缩成 4 行提词卡（实测样本：膨胀率仅 42%，源文档一处的四条机制被压成一行）。本函数给出可计算的丰富度度量，
    供 gate_check 第 5 指标判定。

    口径（重要）：original 必须传**过滤后源**（clean_only.md）——未过滤源含
    OCR 噪音会虚高分母（实测：未过滤 36% / 过滤后 100%）。

    Args:
        original: 源文（清洗/过滤后 md 全文）。
        rewritten: 重排后笔记全文。

    Returns:
        膨胀率 float（0~∞，>1 表示扩写）；源为空返回 0.0（交由调用方判边界）。
    """
    original = original if isinstance(original, str) else ""
    rewritten = rewritten if isinstance(rewritten, str) else ""
    s = _content_len(original)
    if s == 0:
        return 0.0
    return _content_len(rewritten) / s


def _structured_carry(note: str) -> int:
    """笔记中结构化载体（表格行+代码行）的内容量——聚合豁免检测用。

    低膨胀率有两种成因：①合理聚合（逐例展开→语法表+代表例，信息无损重组，
    实测某聚合章 31%：源179行代码聚合成11行语法表+9行代表例）；②偷工压缩
    （保留结论删推导，实测压缩样本 42%：四条机制压成一行，无任何结构化承载）。
    两者的区分信号 = 笔记里有没有承载源信息的结构化形式（表格/代码）。
    """
    if not isinstance(note, str):
        return 0
    carry = 0
    in_code = False
    for ln in note.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            carry += len(s)                     # 代码行全量计入（保留的示例/公式）
        elif s.startswith("|"):
            carry += len(s)                     # 表格行计入（语法表/对照表）
    return carry


def _kp_cover(note: str) -> int:
    """笔记知识点结构数：###/## 标题数（含知识点小节+结构化分节）。"""
    if not isinstance(note, str):
        return 0
    return len(re.findall(r"^#{2,3} ", note, re.M))


def _src_sections(src: str) -> int:
    """源小节数：## 编号标题数（如 '## 3.1 xxx' / '## 9.2.2 xxx' / '## 1，题目'）。

    编号后容错中英文标点/空格（教材体 '## 3.1 Selector'、编号体 '## 1，题目'、
    '## 8. 请从...'都要命中——漏数会让豁免分母虚小、覆盖率虚高，实测样本
    被误豁免 2900% 即此因）。
    """
    if not isinstance(src, str):
        return 0
    n = len(re.findall(r"^## \d+[.\d]*[ ，,．.、]", src, re.M))
    return n if n else len(re.findall(r"^## ", src, re.M))


def _unit_ratios(original: str, rewritten: str) -> list:
    """逐单元膨胀率：按编号标题把源与笔记切成对应单元，算每单元内容量比。

    豁免判据 v3 的核心度量——「聚合」与「压缩」在总体膨胀率上都是低值，
    但逐单元不同：聚合是同构行合并成表，单元级信息无损；压缩
    （压缩样本）是每题答案都瘦，逐题膨胀率中位仅 21%（实测）。

    单元切分：源按 `## N[标点]` 编号标题切，笔记按 `### N ·` 或
    `### N ·` 切（两种排版体都认——详解体用后者，漏认会让
    逐单元检查被静默跳过、unit_median 兜底 1.0 掩盖压缩，2026-09-22 实测）；
    只统计两侧都存在且源单元内容量 >50 字符的单元（滤标题残段）。
    """
    def split_by_num(text, pat):
        parts = {}
        if not isinstance(text, str):
            return parts
        matches = list(re.finditer(pat, text, re.M))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            parts[int(m.group(1))] = _content_len(text[m.start():end])
        return parts

    src_parts = split_by_num(original, r"^##\s*(\d+)[.\d]*[ ，,．.、]")
    note_parts = split_by_num(rewritten, r"^###\s*(?:知识点\s*)?(\d+)\s*·")
    ratios = []
    for num, s_len in src_parts.items():
        if num in note_parts and s_len > 50:
            ratios.append(note_parts[num] / s_len)
    return ratios


def expansion_verdict(original: str, rewritten: str, threshold: float = 0.80,
                      dedup_threshold: float = 0.65, dedup: bool = False) -> dict:
    """丰富度判定（膨胀率 + 聚合豁免，v0.4.5 门禁第 5 指标的判定入口）。

    判定流程（豁免检测方案 v6，2026-09-21 定稿，三区间制）：
      ① 膨胀率 ≥ 0.80 → PASS（丰富度达标）
      ② 0.30 ≤ 膨胀率 < 0.80 → 豁免候选区，**三条件同时满足**才豁免：
         a. 知识点覆盖：笔记标题结构数 ≥ 源小节数 × 0.8（覆盖不缩水）
         b. 结构化承载：笔记表格行 + 代码行 ≥ 10 行（聚合的物理形态）
         c. 逐单元膨胀率中位 ≥ 0.40（每个信息单元不能瘦过四成——
            区分"重组"与"压缩"的唯一可靠信号）
         三条件满足 = 合理聚合放行（exempt=True，warning 记录）
      ③ 膨胀率 < 0.30 → FAIL（绝对红线：内容量不足三成，任何形式都不合理）

    判据演化教训（勿回退）：
      v1「承载字符/源字符 ≥60%」数学上自相矛盾——聚合就是 100 字压成 20 字
      表格承载同样信息，承载字符天然远小于源（某聚合章仅 17% 却是合格聚合）。
      v2 覆盖+承载双条件 → 压缩样本（每题中位 21%）被误豁免 322%。
      v3 逐单元中位 ≥65% → 对"源单元并入笔记无编号概述段"的排版差异过敏
      （某章 77% 合格笔记被误杀——单元1并入概述段，编号对不上）。
      v4 红线65%一刀切 → 多个合格聚合章（31%~61%）全部误杀。
      v5 红线40% → 某聚合章 31% 撞线。
      v6 定稿：红线 30% + 豁免区 30~80% + 逐单元中位 ≥40%。实测全部校准样本
      不误杀（31%~130% 全过），压缩样本 42%（逐单元中位 21%）被拦。

    阈值参数说明：threshold/dedup_threshold 来自 configs/user_prefs.yaml；
    红线 0.30 与逐单元线 0.40 为定稿常量（有多组合格笔记+压缩样本实测锚定），如需调整
    须重新走数据校准流程。

    Args:
        original: 过滤后源全文。
        rewritten: 笔记全文。
        threshold: 正常膨胀率下限（configs/user_prefs.yaml expansion_ratio.general）。
        dedup_threshold: 去重场景下限（expansion_ratio.dedup）。
        dedup: 是否按去重场景判定。

    Returns:
        {"ratio", "threshold", "carry", "kp_note", "kp_src", "kp_cover",
         "unit_median", "ok", "exempt", "reason"}
        - ok: 最终判定
        - exempt: 是否触发聚合豁免（True 时 ok=True 但 reason 说明）
    """
    eff = dedup_threshold if dedup else threshold
    ratio = expansion_ratio(original, rewritten)
    note_kp = _kp_cover(rewritten)
    src_kp = _src_sections(original)
    kp_cover = note_kp / src_kp if src_kp else 1.0
    carry = _structured_carry(rewritten)
    ratios = _unit_ratios(original, rewritten)
    unit_median = sorted(ratios)[len(ratios) // 2] if ratios else 1.0
    res = {"ratio": round(ratio, 3), "threshold": eff, "carry": carry,
           "kp_note": note_kp, "kp_src": src_kp,
           "kp_cover": round(kp_cover, 2), "unit_median": round(unit_median, 2),
           "ok": True, "exempt": False, "reason": ""}
    if ratio >= eff:
        res["reason"] = f"膨胀率 {ratio:.0%} ≥ {eff:.0%}，丰富度达标"
        return res
    # 红线下方：直接 FAIL
    if ratio < 0.30:
        res["ok"] = False
        res["reason"] = (f"膨胀率 {ratio:.0%} < 绝对红线 30%——内容量不足三成，"
                         f"任何聚合形式都不合理（参考：逐单元中位 {unit_median:.0%}）")
        return res
    # 豁免候选区 [0.30, threshold)：查覆盖 + 承载 + 逐单元三条件
    kp_ok = src_kp == 0 or kp_cover >= 0.8
    carry_ok = carry >= 10
    unit_ok = not ratios or unit_median >= 0.40
    if kp_ok and carry_ok and unit_ok:
        res["ok"] = True
        res["exempt"] = True
        res["reason"] = (f"膨胀率 {ratio:.0%} 在豁免区 [30%~{eff:.0%})，"
                         f"知识点覆盖 {kp_cover:.0%}（{note_kp}/{src_kp}）+ 结构化承载 "
                         f"{carry} 行 + 逐单元中位 {unit_median:.0%} → 合理聚合，豁免放行")
    else:
        miss = []
        if not kp_ok:
            miss.append(f"知识点覆盖不足（{note_kp}/{src_kp}={kp_cover:.0%} < 80%）")
        if not carry_ok:
            miss.append(f"无结构化承载（表格+代码仅 {carry} 行 < 10）")
        if not unit_ok:
            miss.append(f"逐单元膨胀率中位 {unit_median:.0%} < 40%（各单元内容被压缩）")
        res["ok"] = False
        res["reason"] = (f"膨胀率 {ratio:.0%} 在豁免区但 {'；'.join(miss)}——疑似偷工")
    return res


def semantic_reconcile(original, rewritten, call=None) -> dict:
    """语义级对账（B2）：调 LLM 判断"概念是否覆盖"，非词级数关键词。

    core 零依赖铁律：LLM 通过 call 回调注入（services 层绑定 prompt + 模型）。
    能检出"词级对账漏掉但概念级缺失"的 case（如 STAR法则 被改写为 四段式描述）。
    LLM 不可用/异常 → 降级返回空缺失（不阻断主流程）。

    Args:
        original: 原文。
        rewritten: 重排后。
        call: 语义对账回调 call(original, rewritten) -> list[str] 缺失概念。

    Returns:
        {"missing": list, "ok": bool}
    """
    if call is None:
        return {"missing": [], "ok": True}
    try:
        missing = call(original, rewritten)
        missing = [str(x) for x in missing if str(x).strip()] if isinstance(missing, list) else []
        return {"missing": missing, "ok": not missing}
    except Exception:  # noqa: BLE001 LLM 失败降级，不阻断
        return {"missing": [], "ok": True}


# ── 阶段 5 · fail-closed 验证门禁（每块独立修补额度）──
_SCORE_TARGET = 95  # 评分目标线（95+ 可教；80-94 偏浅；<80 不合格）


def gate(mech_ok: bool, quality_issues: list, score: float,
         retries_left: int, score_threshold: int = _SCORE_TARGET) -> dict:
    """fail-closed 验证门禁：判断某块 通过 / 修补 / 挂起。

    fail-closed：任一硬项不达标（机械对账失败/质检真问题）→ 不能"通过"。
    评分 < 阈值 → 偏浅，需补详细度（软）。修补次数用完仍不达标 → 挂起等人工。

    Args:
        mech_ok: 机械对账是否通过（关键点覆盖率 ≥90%）。
        quality_issues: GLM 质检问题清单（已复核，真问题）。
        score: GLM 评分 0-100。
        retries_left: 该块剩余修补次数（每块独立，各块互不挤占）。
        score_threshold: 评分目标线。

    Returns:
        {"pass": bool, "action": "pass"|"repair"|"hang", "reason": str}
    """
    reasons = []
    if not mech_ok:
        reasons.append("机械对账失败（关键点缺失，须补）")
    if quality_issues:
        reasons.append(f"质检 {len(quality_issues)} 条真问题")
    if score < score_threshold:
        reasons.append(f"评分 {score} < {score_threshold}（偏浅，补详细度）")
    if not reasons:
        return {"pass": True, "action": "pass", "reason": ""}
    if retries_left > 0:
        return {"pass": False, "action": "repair", "reason": "；".join(reasons)}
    return {"pass": False, "action": "hang",
            "reason": "；".join(reasons) + "；修补次数用完，挂起待人工"}
