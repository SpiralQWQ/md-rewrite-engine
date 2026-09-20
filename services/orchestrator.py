"""services/orchestrator.py — 主流程编排（读 → 切 → 滚动重排 → 验证 → 写）。

单向依赖：core（assemble/chunk/rewrite/verify）+ providers（file_io）+ services/llm。
LLM 通过 `_call` 依赖注入（默认真实 call_llm；测试注入 fake）。

流程（对应 v6 流程设计 ①②③）：
  清洗后 md → assemble 标题树 → chunk 切块
  → rolling_compile（run_rewrite 注入：重排+摘要+边界合并）
  → 每单元：质检（双模型） + 对账 + 评分（verify）
  → 不合格打回重写（max_rewrite_retries）→ 拼接输出 → 写 md
"""
from __future__ import annotations

import json
import os
import tempfile
import time

from core import assemble as A
from core import chunk as CH
from core import concepts as CN
from core import md_index as MI
from core import rewrite as RW
from core import search as SR
from core import toc as TOC
from core import verify as V
from providers import git_io as GIT
from providers.file_io import read_md, scan_md_dir, write_md
from services.llm import run_quality, run_reconcile, run_rewrite, run_scoring


def _make_summarize_fn(glossary: str, spec: dict | None, call):
    """把 run_rewrite 适配成 rolling_compile 的 summarize_fn 契约。"""
    def fn(text: str, prev_summary: str):
        return run_rewrite(text, prev_summary, glossary, spec, _call=call)
    return fn


def _maybe_git_commit(path: str) -> None:
    """B1：产出落盘后 git 自动提交（非 git 仓库/提交失败静默跳过，不阻断）。"""
    if GIT.in_git_repo(path):
        GIT.commit_file(path, f"rewrite: {os.path.basename(path)}")


def assemble_chunks(text: str, max_chars: int = 8000, overlap_chars: int = 200) -> list:
    """物理分块（B 方向能力函数）：全文 → 段落边界切块，超长兜底。

    供本体主控时调用——先拿物理块，再逐块重排（带全局地图）。空/异常 → []。
    """
    if not isinstance(text, str) or not text.strip():
        return []
    blocks = A.assemble(text)
    return CH.chunk_blocks(blocks, max_chars=max_chars, overlap_chars=overlap_chars)


def concept_map(text: str, chunks: list = None) -> list:
    """候选概念地图（B 方向辅助，Task-08）：粗体术语 + 块标题，供本体重排前参考。

    本体据它抽真正的核心概念清单（判断权在本体）；本函数只给候选，去重保序。
    """
    seen = set()
    out = []
    terms = CN.extract_terms(text) if isinstance(text, str) else []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    for c in (chunks or []):
        for t in c.get("breadcrumb", []) or []:
            if t and t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
    return out


def chunks_with_context(chunks: list) -> list:
    """逐块重排的上下文包（B 方向辅助，Task-10）：每块带"后文预告"（下一块标题）。

    供本体带全局重排——每块知道前面讲了啥（本体自维护前文摘要）+ 后面将讲啥（next_title），
    防隔离。返回 [{"index", "text", "next_title"}]。
    """
    out = []
    n = len(chunks)
    for i, c in enumerate(chunks):
        next_title = ""
        if i + 1 < n:
            bc = chunks[i + 1].get("breadcrumb", []) or []
            next_title = bc[-1] if bc else ""
        out.append({"index": i, "text": c.get("text", ""), "next_title": next_title})
    return out


def write_output(note_text: str, source_text: str = "", out_dir: str = "",
                 note_name: str = "note.md", source_subdir: str = "源数据") -> dict:
    """输出笔记 + 转写外置源文件（B 方向能力函数，附录外置）。

    笔记写 out_dir/note_name；转写原文写 out_dir/<source_subdir>/转写.md——原文外置，
    不干扰 AI 教学上下文（需要溯源时再查源文件）。空/异常 → error dict。

    Returns:
        {"ok", "note_path", "source_path", "error"?}
    """
    if not isinstance(note_text, str) or not note_text or not out_dir:
        return {"ok": False, "error": "缺少笔记内容或输出目录", "note_path": "", "source_path": ""}
    try:
        # 篇内目录后处理（v0.3.1）：从标题自动生成 TOC 插入（幂等），AI 无需手写
        note_text, _ = TOC.build_toc(note_text)
        note_path = os.path.join(out_dir, note_name)
        write_md(note_path, note_text)
        src_path = ""
        if isinstance(source_text, str) and source_text:
            src_dir = os.path.join(out_dir, source_subdir)
            src_path = os.path.join(src_dir, "转写.md")
            write_md(src_path, source_text)
        return {"ok": True, "note_path": note_path, "source_path": src_path}
    except Exception as e:  # noqa: BLE001 输出失败转 dict
        return {"ok": False, "error": f"输出失败: {e}", "note_path": "", "source_path": ""}


def _load_state(path: str) -> dict:
    """B3：读断点状态文件（JSON）。无/损坏 → {}。"""
    if not isinstance(path, str) or not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(path: str, data: dict) -> None:
    """B3：写断点状态文件（JSON，原子写防中断）。失败静默（不阻断）。"""
    if not isinstance(path, str) or not path:
        return
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=parent or ".", prefix=".st_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except (OSError, UnboundLocalError):
            pass


def process(md_path: str, output_path: str = "",
            spec: dict | None = None, glossary: str = "",
            max_chars: int = 8000, overlap_chars: int = 200,
            max_rewrite_retries: int = 1, state_path: str = "", branch: bool = False,
            _call=None) -> dict:
    """对一篇清洗后 md 执行完整流水线。

    Args:
        md_path: 清洗后 md 文件路径。
        output_path: 输出路径；空则不写文件（仅返回文本）。
        spec: note_style_spec 字典（None 用 llm 通用要求）。
        glossary: 术语表文本（注入重排）。
        max_chars / overlap_chars: 切块参数。
        max_rewrite_retries: 单单元验证不过时的重排重试次数。
        state_path: 断点状态文件路径（B3）；空则不启用断点。
        branch: 若 True 且 output 在 git 仓库，重排前建 rewrite-<ts> 分支（C2 可回滚）。
        _call: LLM 调用函数注入（默认 providers.llm_client.call_llm）。

    Returns:
        {"ok", "issues", "output", "output_path", "units", "inferred", "resumed", "error"?}
        - inferred: 输出中 [AI推断] 标记数（D5，供人工抽查）
        - low_conf: 输出中 [低置信] 标记数（B4，供人工抽查）
        - diff: 产出后 git diff --stat 摘要（C2 branch 模式；非 branch 为空串）
        - resumed: 是否命中断点续跑（B3：已完成直接返回缓存，跳过 LLM 重调）
    """
    from providers.llm_client import call_llm  # noqa: WPS433 延迟导入避免循环
    call = _call or call_llm
    max_rewrite_retries = max(0, max_rewrite_retries)  # 负数 → 0（至少跑 1 轮验证，不静默跳过）

    # C2 git 分支保护：重排前建分支（rewrite-<ts>，可回滚），非 git 仓库跳过
    if branch and output_path and GIT.in_git_repo(output_path):
        GIT.create_branch(output_path, f"rewrite-{int(time.time())}")

    # B3 断点续跑：状态已完成 且 输入未变（src_mtime 匹配）→ 返回缓存，跳过 LLM 重调
    state = _load_state(state_path)
    src_mtime = int(os.path.getmtime(md_path)) if md_path and os.path.isfile(md_path) else None
    if state.get("done") is not None and state.get("total") is not None \
            and state["done"] >= state["total"] and state.get("output") is not None \
            and state.get("src_mtime") == src_mtime:
        return {"ok": state.get("ok", False), "issues": state.get("issues", []),
                "output": state["output"], "output_path": output_path,
                "units": state.get("total", 0), "inferred": state.get("inferred", 0),
                "resumed": True, "diff": ""}

    # 终点一致性：任何流水线异常都转成统一 error dict（不向调用方抛裸异常）
    try:
        result = _process_run(md_path, output_path, spec, glossary, max_chars,
                              overlap_chars, max_rewrite_retries, call, state_path, src_mtime)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"流水线异常: {e}", "issues": [],
                "output": "", "output_path": output_path, "units": 0,
                "inferred": 0, "low_conf": 0, "resumed": False, "diff": ""}
    result["resumed"] = False
    if branch and output_path:
        result["diff"] = GIT.diff_summary(output_path)  # C2 diff 预览
    else:
        result["diff"] = ""
    return result


def _process_run(md_path, output_path, spec, glossary, max_chars,
                 overlap_chars, max_rewrite_retries, call, state_path="", src_mtime=None) -> dict:
    """process 实际执行体（异常由外层统一转 dict，保证失败模式终点一致）。"""
    text = read_md(md_path)
    if text is None:
        return {"ok": False, "error": f"文件不存在: {md_path}", "issues": [],
                "output": "", "output_path": output_path, "units": 0,
                "inferred": 0, "low_conf": 0, "resumed": False, "diff": ""}

    # ① 标题树 + 切块
    blocks = A.assemble(text)
    chunks = CH.chunk_blocks(blocks, max_chars=max_chars, overlap_chars=overlap_chars)
    if not chunks:
        return {"ok": False, "error": "解析后无内容可处理", "issues": [],
                "output": "", "output_path": output_path, "units": 0,
                "inferred": 0, "low_conf": 0, "resumed": False, "diff": ""}

    # ② 滚动编译（重排 + 摘要贯穿 + 边界合并）
    summarize = _make_summarize_fn(glossary, spec, call)
    units = RW.rolling_compile(chunks, summarize)

    # ③ 逐单元验证（双模型质检 + 对账 + 评分），不合格打回重写
    issues: list = []
    rewritten_parts: list = []
    for unit in units:
        orig, rw = unit["text"], unit["rewritten"]
        for attempt in range(max_rewrite_retries + 1):
            v = V.check(orig, rw)                  # 机械对账 + 评分
            q = run_quality(orig, rw, _call=call)  # 双模型质检（另一 AI 挑错）
            # B2 语义级对账（概念覆盖，非词级；LLM 失败降级）
            sr = V.semantic_reconcile(orig, rw, lambda o, w: run_reconcile(o, w, _call=call))
            if not sr["ok"]:
                q.append(f"语义缺失: {', '.join(sr['missing'][:3])}")
            # LLM 质量评分门槛（增强 9）
            if run_scoring(rw, spec, _call=call) < 80:
                q.append("LLM 质量评分 < 80")
            if v["pass"] and not q:
                break                              # 本单元通过
            if attempt == max_rewrite_retries:
                # 重试耗尽仍不过 → 计入最终问题
                issues.extend(v["issues"] if v["issues"] else [])
                issues.extend(q)
                break
            # 打回重写：附问题清单让 AI 修正
            hint = "; ".join((v["issues"] + q)[-3:])
            rw, _s, _m = run_rewrite(orig, unit["summary"], glossary, spec,
                                     hint=hint, _call=call)
        rewritten_parts.append(rw)
        # B3 断点：每单元完成写状态（done 递增，中断后进度可查/续跑）
        if state_path:
            _save_state(state_path, {"done": len(rewritten_parts), "total": len(units),
                                     "ok": False, "output": "\n\n".join(rewritten_parts),
                                     "src_mtime": src_mtime})

    output = "\n\n".join(rewritten_parts)
    if output_path:
        write_md(output_path, output)
        _maybe_git_commit(output_path)  # B1 自动提交（非 git 仓库跳过）

    if state_path:
        # B3：完成态（ok + issues + inferred + src_mtime），供重跑直接续用
        _save_state(state_path, {"done": len(units), "total": len(units),
                                 "ok": not issues, "issues": issues, "output": output,
                                 "inferred": output.count("[AI推断]"),
                                 "src_mtime": src_mtime})

    return {
        "ok": not issues,
        "issues": issues,
        "output": output,
        "output_path": output_path,
        "units": len(units),
        "inferred": output.count("[AI推断]"),  # D5 推断点计数（供人工抽查）
        "low_conf": output.count("[低置信]"),  # B4 低置信标记计数（供人工抽查）
    }


def build_course_index(course_dir: str, output_path: str = "") -> dict:
    """扫描课程目录 → 生成总索引 index.md（D1 知识点地图）。

    编排：读文件(providers) → 元数据提取(core/md_index 纯函数) → 渲染 → 原子写。
    任何异常统一转 error dict（终点一致性：失败模式一致，不抛裸异常）。

    Args:
        course_dir: 课程笔记目录（含多篇笔记 md）。
        output_path: 输出 index.md 路径；空默认写 course_dir/index.md。
            ⚠️ 建议用 index.md 标准名——扫描会排除任意层级的 index.md 防自扫。

    Returns:
        {"ok", "notes", "index_path", "output", "error"?}
    """
    try:
        return _build_index_run(course_dir, output_path)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"索引生成异常: {e}", "notes": 0,
                "index_path": output_path, "output": ""}


def _build_index_run(course_dir: str, output_path: str) -> dict:
    """build_course_index 实际执行体（异常由外层统一转 dict）。"""
    if not course_dir or not isinstance(course_dir, str) or not os.path.isdir(course_dir):
        return {"ok": False, "error": f"课程目录不存在: {course_dir}", "notes": 0,
                "index_path": output_path, "output": ""}
    out = output_path or os.path.join(course_dir, "index.md")
    out_abs = os.path.abspath(out)
    files = [p for p in scan_md_dir(course_dir)
             if os.path.abspath(p) != out_abs               # 防索引自扫（自定义输出到子目录也会被递归扫回）
             and os.path.basename(p).lower() != "index.md"]
    notes = []
    for p in files:
        text = read_md(p)
        if not text or not text.strip():
            continue
        fm = MI.parse_frontmatter(text)
        notes.append({
            "file": os.path.basename(p),
            "title": fm.get("title") or MI.first_heading(text) or os.path.basename(p),
            "summary": fm.get("description", "") or MI.summary_line(text),
            "tags": fm.get("tags", []),
        })
    if not notes:
        return {"ok": False, "error": "目录下无有效笔记 md", "notes": 0,
                "index_path": output_path, "output": ""}
    course_name = os.path.basename(os.path.normpath(course_dir))
    index_text = MI.build_index(course_name, notes)
    out = output_path or os.path.join(course_dir, "index.md")
    write_md(out, index_text)
    _maybe_git_commit(out)  # B1 自动提交
    return {"ok": True, "notes": len(notes), "index_path": out, "output": index_text}


def validate_course_links(course_dir: str) -> dict:
    """扫描课程目录 → 校验每篇笔记的 [[链接]] 目标存在（D2 悬空链接检测）。

    已知目标 = 课程内所有笔记文件名（带 .md 与不带两种，容错链接写法）。
    缺目标仅 warning 不阻断（OKFy 约定），供人工抽查。

    Returns:
        {"ok", "checked", "broken_total", "broken",
         "relation_missing_total", "relation_broken_total", "relation_issues",
         "citation_missing_total", "citation_issues", "error"?}
        - ok: 无悬空链接 且 无关联字段悬空
        - checked: 已校验笔记数
        - broken_total: 悬空链接总数
        - broken: [{"file", "links"}] 有悬空链接的笔记
        - relation_missing_total: 关联字段缺失数（warning）
        - relation_broken_total: 关联字段指向不存在目标数
        - relation_issues: [{"file", "missing", "broken"}] 关联字段 issue 明细
        - citation_missing_total: 示例/原句缺出处行数（D4 抽查，warning）
        - citation_issues: [{"file", "lines"}] 缺出处行明细
        - conf_issues_total: 置信度异常数（缺失/非法，D6 warning）
        - conf_issues: [{"file", "issues"}] 置信度 issue 明细
        - low_conf: list[str] confidence=low 的笔记（人工抽查清单）
        - schema_issues_total: frontmatter schema 异常笔记数（C3d warning）
        - schema_issues: [{"file", "missing", "type_errors"}] schema issue 明细
    """
    try:
        return _validate_links_run(course_dir)
    except Exception as e:  # noqa: BLE001 终点一致性
        return {"ok": False, "error": f"链接校验异常: {e}", "checked": 0,
                "broken_total": 0, "broken": []}


def _validate_links_run(course_dir: str) -> dict:
    """validate_course_links 实际执行体（异常由外层统一转 dict）。"""
    if not course_dir or not isinstance(course_dir, str) or not os.path.isdir(course_dir):
        return {"ok": False, "error": f"课程目录不存在: {course_dir}", "checked": 0,
                "broken_total": 0, "broken": []}
    files = [p for p in scan_md_dir(course_dir)
             if os.path.basename(p).lower() != "index.md"]
    if not files:
        return {"ok": False, "error": "目录下无有效笔记 md", "checked": 0,
                "broken_total": 0, "broken": []}
    known = set()  # 已知目标：文件名带扩展 + 不带扩展（容错 [[a.md]] / [[a]]）
    for p in files:
        base = os.path.basename(p)
        known.add(base)
        known.add(os.path.splitext(base)[0])
    broken_files = []
    total = 0
    checked = 0
    rel_missing_total = 0
    rel_broken_total = 0
    rel_issues = []  # 关联字段 issue：{"file", "missing", "broken"}
    cit_missing_total = 0
    cit_issues = []  # 缺出处行：{"file", "lines"}
    conf_issues_total = 0
    conf_issues = []  # 置信度 issue（缺失/非法）：{"file", "issues"}
    low_conf = []     # confidence=low 的笔记（合法但进人工抽查清单）
    schema_issues = []  # frontmatter schema issue：{"file", "missing", "type_errors"}
    schema_issues_total = 0
    for p in files:
        text = read_md(p)
        if not text:
            continue
        checked += 1
        r = V.validate_links(text, known)
        if r["broken"]:
            broken_files.append({"file": os.path.basename(p), "links": r["broken"]})
            total += len(r["broken"])
        # D3 关联字段校验（frontmatter prerequisites/next/related）
        fm = MI.parse_frontmatter(text)
        rr = V.validate_relations(fm, known)
        rel_missing_total += len(rr["missing"])
        rel_broken_total += len(rr["broken"])
        if rr["missing"] or rr["broken"]:
            rel_issues.append({"file": os.path.basename(p),
                               "missing": rr["missing"], "broken": rr["broken"]})
        # D4 条目级引用抽查（示例/原句缺出处）
        missing_lines = V.find_missing_source(text)
        cit_missing_total += len(missing_lines)
        if missing_lines:
            cit_issues.append({"file": os.path.basename(p), "lines": missing_lines})
        # D6 置信度落值校验（confidence 缺失/非法 → issue；low → 人工抽查清单）
        rc = V.validate_confidence(fm)
        conf_issues_total += len(rc["issues"])
        if rc["issues"]:
            conf_issues.append({"file": os.path.basename(p), "issues": rc["issues"]})
        elif str(fm.get("confidence", "")).strip().lower() == "low":
            low_conf.append(os.path.basename(p))
        # C3d frontmatter schema 校验（必填 title/type + tags 类型）
        fs = V.validate_frontmatter_schema(fm, ["title", "type"], {"tags": list})
        if not fs["ok"]:
            schema_issues.append({"file": os.path.basename(p),
                                  "missing": fs["missing"], "type_errors": fs["type_errors"]})
            schema_issues_total += 1
    return {"ok": total == 0 and rel_broken_total == 0, "checked": checked,
            "broken_total": total, "broken": broken_files,
            "relation_missing_total": rel_missing_total,
            "relation_broken_total": rel_broken_total,
            "relation_issues": rel_issues,
            "citation_missing_total": cit_missing_total,
            "citation_issues": cit_issues,
            "conf_issues_total": conf_issues_total,
            "conf_issues": conf_issues,
            "low_conf": low_conf,
            "schema_issues_total": schema_issues_total,
            "schema_issues": schema_issues}


def build_concepts(course_dir: str, output_dir: str = "") -> dict:
    """扫描课程 → 提取核心概念 → 生成概念页（D7，一概念一页跨讲累积）。

    机械打底：从各篇粗体英文术语提取候选，聚合"出现讲次 + 摘录定义"，写到
    concepts/ 目录；人工可后续完善定义与关系。异常统一转 dict（终点一致性）。

    Args:
        course_dir: 课程笔记目录。
        output_dir: 概念页输出目录；空默认写 course_dir/concepts。

    Returns:
        {"ok", "concepts", "pages_dir", "pages", "error"?}
        - concepts: 生成概念页数
        - pages: [{"name", "file"}] 概念页清单
    """
    try:
        return _build_concepts_run(course_dir, output_dir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"概念页生成异常: {e}", "concepts": 0,
                "pages_dir": output_dir, "pages": []}


def _build_concepts_run(course_dir: str, output_dir: str) -> dict:
    """build_concepts 实际执行体（异常由外层统一转 dict）。"""
    if not course_dir or not isinstance(course_dir, str) or not os.path.isdir(course_dir):
        return {"ok": False, "error": f"课程目录不存在: {course_dir}", "concepts": 0,
                "pages_dir": output_dir, "pages": []}
    files = [p for p in scan_md_dir(course_dir)
             if os.path.basename(p).lower() != "index.md"]
    if not files:
        return {"ok": False, "error": "目录下无有效笔记 md", "concepts": 0,
                "pages_dir": output_dir, "pages": []}
    texts = {}
    term_files = {}  # term_lower -> set(文件基名)
    term_orig = {}   # term_lower -> 原始术语（保留大小写）
    for p in files:
        text = read_md(p)
        if not text:
            continue
        base = os.path.basename(p)
        texts[base] = text
        for term in CN.extract_terms(text):
            term_files.setdefault(term.lower(), set()).add(base)
            term_orig.setdefault(term.lower(), term)
    if not term_files:
        return {"ok": False, "error": "未提取到粗体英文术语（无概念候选）", "concepts": 0,
                "pages_dir": output_dir, "pages": []}
    out_dir = output_dir or os.path.join(course_dir, "concepts")
    pages = []
    for term_low in sorted(term_files):
        concept = term_orig.get(term_low, term_low)
        occurrences = []
        for base in sorted(term_files[term_low]):
            contexts = CN.find_context(texts[base], concept)
            occurrences.append({"file": base, "contexts": contexts})
        page_text = CN.build_concept_page(concept, occurrences)
        safe = term_low.replace(" ", "_")
        page_path = os.path.join(out_dir, f"{safe}.md")
        write_md(page_path, page_text)
        _maybe_git_commit(page_path)  # B1 自动提交
        pages.append({"name": concept, "file": page_path})
    return {"ok": True, "concepts": len(pages), "pages_dir": out_dir, "pages": pages}


def search_course(course_dir: str, query: str) -> dict:
    """扫描课程 → 词法检索（D8，AI 能"找"知识点而非全读）。

    Returns:
        {"ok", "query", "results", "error"?}
        - results: [{"file", "score", "hits"}] 按命中数降序
    """
    try:
        return _search_course_run(course_dir, query)
    except Exception as e:  # noqa: BLE001 终点一致性
        return {"ok": False, "error": f"检索异常: {e}", "query": query, "results": []}


def _search_course_run(course_dir: str, query: str) -> dict:
    """search_course 实际执行体（异常由外层统一转 dict）。"""
    if not course_dir or not isinstance(course_dir, str) or not os.path.isdir(course_dir):
        return {"ok": False, "error": f"课程目录不存在: {course_dir}", "query": query,
                "results": []}
    files = [p for p in scan_md_dir(course_dir)
             if os.path.basename(p).lower() != "index.md"]
    texts = {}
    for p in files:
        text = read_md(p)
        if text:
            texts[os.path.basename(p)] = text
    if not texts:
        return {"ok": False, "error": "目录下无有效笔记 md", "query": query, "results": []}
    results = SR.search(texts, query)
    if not results:
        return {"ok": False, "error": "无匹配结果", "query": query, "results": []}
    return {"ok": True, "query": query, "results": results}


def process_course(course_dir: str, state_path: str = "", _call=None) -> dict:
    """增量批处理课程（C3a）：只处理 mtime 变化的笔记，跳过未变更。

    state_path 记录每篇处理后的 mtime；已处理且未变 → 跳过。
    对每篇执行完整重排（process），不写输出（仅验证质量）。
    异常统一转 dict。

    Returns:
        {"ok", "processed", "skipped", "errors", "error"?}
        - processed: 本批处理数
        - skipped: 未变更跳过数
        - errors: [{"file", "error"}] 处理失败明细
    """
    try:
        return _process_course_run(course_dir, state_path, _call)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"批处理异常: {e}", "processed": 0,
                "skipped": 0, "errors": []}


def _process_course_run(course_dir: str, state_path: str, call) -> dict:
    """process_course 实际执行体（异常由外层统一转 dict）。"""
    if not course_dir or not isinstance(course_dir, str) or not os.path.isdir(course_dir):
        return {"ok": False, "error": f"课程目录不存在: {course_dir}", "processed": 0,
                "skipped": 0, "errors": []}
    files = [p for p in scan_md_dir(course_dir)
             if os.path.basename(p).lower() != "index.md"]
    if not files:
        return {"ok": False, "error": "目录下无有效笔记 md", "processed": 0,
                "skipped": 0, "errors": []}
    state = _load_state(state_path) if state_path else {}
    processed = skipped = 0
    errors = []
    for p in files:
        try:
            mtime = int(os.path.getmtime(p))
            base = os.path.basename(p)
            if state.get(base) == mtime:  # 增量：已处理且未变 → 跳过
                skipped += 1
                continue
            r = process(p, _call=call)  # 完整重排（注入 call；默认真实 LLM）
            if r.get("ok"):
                processed += 1
                if state_path:
                    state[base] = mtime
                    _save_state(state_path, state)
            else:
                errors.append({"file": base,
                               "error": "; ".join(r.get("issues", [])[:2]) or r.get("error", "")})
        except Exception as e:  # noqa: BLE001 单篇失败不阻断批处理
            errors.append({"file": os.path.basename(p), "error": str(e)})
    return {"ok": not errors, "processed": processed, "skipped": skipped, "errors": errors}
