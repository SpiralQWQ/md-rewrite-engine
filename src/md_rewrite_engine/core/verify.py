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
