"""services/llm.py — LLM prompt 组装 + 重排/质检/评分调用（服务域）。

单向依赖：providers/llm_client（真实调用）+ 配置 spec/glossary 由调用方注入。
AI 输出统一要求 JSON，解析用 best-effort（JSON 找块 + 兜底），防 AI 输出不规范崩管线。

三个环节（对应增强 4/7/9）：
- run_rewrite   → 滚动重排，返回 (rewritten, summary, merge_with_next)
- run_quality   → 双模型质检，另一个 AI 挑错，返回问题列表
- run_scoring   → 质量评分，返回 0-100
"""
from __future__ import annotations

import json
import re

from md_rewrite_engine.providers.llm_client import call_llm  # noqa: WPS436 (服务域允许依赖 providers)


def _repair_json(text: str) -> str:
    """把 JSON 字符串值内的裸换行/回车替换为转义（模型常输出非法裸换行）。"""
    def _fix(m):
        return m.group(0).replace("\n", "\\n").replace("\r", "\\r")
    # 匹配 JSON 字符串字面量（含内部转义），只修引号内裸换行，不碰结构空白
    return re.sub(r'"(?:[^"\\]|\\.)*"', _fix, text)


def _extract_json(text: str) -> dict:
    """best-effort 解析 AI 输出中的 JSON 对象。

    先找顶层 {…} 块 try 解析；裸换行修复后重试；仍失败按 key:value 行粗解析。
    """
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        raw = m.group(0)
        for candidate in (raw, _repair_json(raw)):
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError):
                continue
    # 兜底：逐行提取 key: value
    out = {}
    for line in text.splitlines():
        km = re.match(r'^\s*["\']?(\w+)["\']?\s*[:：]\s*(.+?)\s*$', line)
        if km:
            out[km.group(1)] = km.group(2).strip(' "\'，。')
    return out


def _spec_text(spec: dict | None) -> str:
    """把 note_style_spec 字典渲染成 prompt 段落（含 AI 友好 4 要素强制，无则给通用要求）。"""
    if not spec:
        return "输出为 Markdown，结构清晰，含标题层级、要点、示例、总结。"
    try:
        fields = spec.get("frontmatter", [])
        struct = spec.get("structure", [])
        rules = spec.get("style_rules", [])
        density = spec.get("info_density", [])
        parts = []
        if fields:
            parts.append("frontmatter 必须含字段：" + "、".join(str(x) for x in fields))
        if struct:
            parts.append("正文结构：" + " → ".join(str(x) for x in struct))
        # AI 友好 4 要素（A1 强制产出标准）
        if density:
            parts.append("【信息密度·强制】每个核心知识点必须完整展开：" + "、".join(str(x) for x in density))
        fpk = spec.get("feynman_per_kp")
        if fpk:
            parts.append(f"【费曼·留白】每个知识点配 {fpk} 道示范思考题（教学线索，AI 可自行展开，不写满教学稿）")
        if spec.get("appendix") == "full_original":
            parts.append("【附录·强制】必须保留完整原文（OCR/GLM 全量），不得概括")
        # v0.4.0 起去 traceability（per_claim 强制每点标来源，与"知识库+留白/不强标出处"冲突，见 note_style_spec
        linking = spec.get("linking")  # D2 互链（v1.3）
        if linking:
            lrules = linking.get("rules") or []
            if lrules:
                parts.append("【互链·强制】" + "；".join(str(x) for x in lrules))
        rel = spec.get("relation_fields")  # D3 关联字段（v1.3）
        if rel:
            parts.append("【关联字段·强制】frontmatter 必须填：" + "、".join(str(x) for x in rel) + "（值 = [[链接]]目标，与互链同步）")
        conf = spec.get("confidence_policy")  # D6 置信度落值（v1.3）
        if conf:
            lv = conf.get("levels") or ["high", "medium", "low"]
            st = conf.get("verify_states") or []
            part = "【置信度·强制】frontmatter confidence 必须实际填写(" + "/".join(str(x) for x in lv) + ")"
            if st:
                part += "；verified(" + "/".join(str(x) for x in st) + ")"
            if conf.get("rule"):
                part += "；" + str(conf["rule"])
            parts.append(part)
        if rules:
            parts.append("风格：" + "；".join(str(x) for x in rules))
        return "\n".join(parts) if parts else "Markdown，结构清晰。"
    except Exception:  # noqa: BLE001 配置异常不阻断
        return "Markdown，结构清晰。"


# ── Prompt 组装（纯函数，可测）──

def build_rewrite_prompt(chunk_text: str, prev_summary: str,
                         glossary: str = "", spec: dict | None = None,
                         hint: str = "") -> tuple:
    """重排 prompt。返回 (system, user)。

    注入三要素（v4 教训：AI 重排必须带上下文）：
      前文摘要（prev_summary）保持全局脉络；术语表（glossary）避免瞎改；
      hint（可选）用于"打回重写"时附修正问题清单。
    """
    spec_block = _spec_text(spec)
    system = (
        "你是教学笔记重排引擎。产出**准确、系统、有启发线索的教学知识库**——AI 读懂后能基于它向你（学习者）教学。\n"
        "原则：① 知识完整（事实/概念/结构/命令都在，AI 不教错、不漏）；"
        "② 教学留白（不写完整讲稿、不写满所有费曼题——给 AI 教学线索与自由发挥空间，具体怎么讲、怎么根据学习者反应调整，由 AI 自行组织）。\n"
        f"{spec_block}\n"
        "【示例·准确】示例务必具体、贴合原文（可参考原文原话表述，不编造）；不强制标注时间戳出处（教学场景不需要）。\n"
        "【顺带清洗】重排即智能清洗——遇到 ASR 错听/拆散数字（mic→Mac、无斑图→Ubuntu、300 0→3000）按上下文理解纠正，不靠词典。\n"
        "【AI推断标注·强制】AI 自行补充超出原文的内容（背景/延伸/推断）必须标 [AI推断]；"
        "原文照搬不标，视频原话与 AI 补充必须可区分。\n"
        "【低置信标注·强制】AI 对存疑内容（不确定/可能不准/数据存疑）标 [低置信]；"
        "确定内容不标，供人工抽查。\n"
        "【改动理由·强制】AI 删除/修改原文内容时，必须在 rewritten 末尾附改动说明行："
        "\"- 改动: 原文片段 → 改写（理由）\"；无删除/修改则不写。\n"
        "【输出前逐字校对】把自己当抄写员逐字核对自己的输出：①命令/参数完整（如 wsl --install 别写成 ws1 install）"
        "；②专有名词拼写与大小写（Ubuntu/Kali/PowerShell/Docker）；③数字不被拆错（3000 别成 300 0）。"
        "发现错字/错命令必须先改对再输出。\n"
        "输出严格 JSON：{\"rewritten\": \"重排后的完整 markdown\", "
        "\"summary\": \"本块要点（≤100字）\", \"merge_with_next\": true或false}"
    )
    user = []
    if prev_summary:
        user.append(f"【前文摘要】{prev_summary}")
    if glossary:
        user.append(f"【术语表】{glossary}")
    user.append(f"【待重排内容】\n{chunk_text}")
    if hint:
        user.append(f"【上一版问题，请修正】{hint}")
    return system, "\n".join(user)


def build_quality_prompt(original: str, rewritten: str) -> tuple:
    """质检 prompt（P4，教学知识库视角）：AI 教学要用，所以查"能否放心教"。

    四组维度（知识库+留白定位，不再比"详细度/费曼4角度"——留白给 AI）：
    ① 知识完整 ② 事实准确 ③ 教学线索 ④ 结构可定位。
    """
    system = (
        "你是严谨的质检员，职责是挑错而非修改。这份笔记是**教学知识库**——AI 会基于它向学习者教学。"
        "你从 **AI 教学视角**审查，查以下维度：\n"
        "① 知识完整：核心概念/命令/数字/专有名词是否都在？有无漏知识点、概念被改没？（知识要够 AI 展开讲，不要求篇幅大）\n"
        "② 事实准确：术语是否统一？ASR 错听是否纠正（mic→Mac）？有无幻觉（编了原文没有的）、概念偷换？\n"
        "③ 教学线索：每个知识点的类比/示例/易错点是否具体、AI 能否据此展开教学？（不要求写满费曼题、不求深度炫技——留白给 AI 自行组织）\n"
        "④ 结构可定位：概述/层级/篇内目录是否清晰，AI 能否快速找到任一知识点？\n"
        "只报真问题（注明位置），不报措辞偏好；**只报基于素材内（原文/转写）能判断的问题，"
        "不报素材外增强建议**（如缺性能对比数据、缺更细版本号——视频没讲的不算问题）。\n"
        "输出严格 JSON：{\"issues\": [\"问题1；位置\", \"问题2\"...]}，无问题输出 {\"issues\": []}"
    )
    user = f"【原文】\n{original}\n\n【重排后】\n{rewritten}"
    return system, user


def build_scoring_prompt(rewritten: str, spec: dict | None = None) -> tuple:
    """评分 prompt（P5，知识库+留白标准）：能否让 AI 放心教学。返回 0-100。"""
    spec_block = _spec_text(spec)
    system = (
        "你是笔记质量评审。这份笔记是**教学知识库**——AI 会基于它向学习者教学。"
        "从 AI 教学视角按规范打 0-100 分。\n"
        "标准：知识完整（核心概念/命令/数字/专名都在，AI 不教错、不漏）+ 结构可定位"
        "（概述/层级/篇内目录清晰）+ 教学线索足（类比/示例/易错点具体，AI 能据此展开）。\n"
        "90+ 知识完整、AI 可放心基于它教学；70-89 有缺料或线索不足需补；<70 知识缺失/事实错误不合格。\n"
        "评分要结合具体问题（缺什么、哪里不可教），不只给分。\n"
        f"{spec_block}\n"
        "输出严格 JSON：{\"score\": 数字, \"reason\": \"一句话理由（含主要缺什么）\"}"
    )
    return system, rewritten


# ── 调用（依赖注入 call_llm，可测）──

def run_rewrite(chunk_text: str, prev_summary: str,
                glossary: str = "", spec: dict | None = None,
                hint: str = "", _call=call_llm) -> tuple:
    """滚动重排一块。返回 (rewritten, summary, merge_with_next)。"""
    system, user = build_rewrite_prompt(chunk_text, prev_summary, glossary, spec, hint)
    resp = _call(user, system=system, model_key="rewrite")
    obj = _extract_json(resp)
    rewritten = obj.get("rewritten") or chunk_text
    summary = obj.get("summary") or rewritten[:80]
    merge = str(obj.get("merge_with_next", "false")).lower() in ("true", "1", "yes")
    return rewritten, summary, merge


def run_quality(original: str, rewritten: str, _call=call_llm) -> list:
    """质检一块。返回问题列表（空 = 通过）。"""
    system, user = build_quality_prompt(original, rewritten)
    resp = _call(user, system=system, model_key="quality_check")
    obj = _extract_json(resp)
    issues = obj.get("issues")
    if isinstance(issues, list):
        return [str(x) for x in issues if str(x).strip()]
    return []


def run_scoring(rewritten: str, spec: dict | None = None, _call=call_llm) -> float:
    """评分一块。返回 0-100（解析失败给 0，交由 verify.check 兜底）。"""
    system, user = build_scoring_prompt(rewritten, spec)
    resp = _call(user, system=system, model_key="scoring")
    obj = _extract_json(resp)
    try:
        return max(0.0, min(100.0, float(obj.get("score", 0))))
    except (TypeError, ValueError):
        return 0.0


def build_reconcile_prompt(original: str, rewritten: str) -> tuple:
    """语义对账 prompt（B2）：GLM 判断概念覆盖，非词级数关键词。

    要点：同义改写（STAR法则 = 四段式描述）算覆盖；只报"真遗漏/改没"的概念。
    """
    system = (
        "你是严谨的概念覆盖审查员。对比原文与重排结果，找出"
        "「原文有但重排后遗漏或改没」的概念（语义级判断，不只数关键词；"
        "同义改写如 STAR法则=四段式描述 算已覆盖）。\n"
        "输出严格 JSON：{\"missing_concepts\": [\"概念名\", ...]}，"
        "无缺失输出 {\"missing_concepts\": []}"
    )
    user = f"【原文】\n{original}\n\n【重排后】\n{rewritten}"
    return system, user


def run_reconcile(original, rewritten, _call=call_llm) -> list:
    """语义级对账：GLM 返回缺失概念列表。解析失败/异常 → []（降级不阻断）。"""
    system, user = build_reconcile_prompt(original, rewritten)
    resp = _call(user, system=system, model_key="reconcile")
    obj = _extract_json(resp)
    missing = obj.get("missing_concepts")
    if isinstance(missing, list):
        return [str(x) for x in missing if str(x).strip()]
    return []
