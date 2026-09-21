# -*- coding: utf-8 -*-
"""scripts/gate_check.py — 本体主控门禁一键检查（v0.4.1 打回闭环落地）。

本体（Claude 对话）重排完必跑本工具，拿到机器指标，决定「通过 / 打回 / 挂起」——
把"靠自觉判断"替换成"机器门禁"。输入就是一份笔记 md + 一份原文 md（同工作流输入）。

检查项：
  ① 机械对账（数字硬判定）：原文基准 → 笔记，数字覆盖率 ≥90% 才过
     （原文若为 _clean.md 时间轴交错格式，自动抽 🎤 语音作基准；普通 md 用全文）
  ② 6 件套完整度：逐知识点查 定义/类比/原理/示例/为什么/易错点（命令块算示例）
  ③ 费曼示范：每知识点 ≥2 个「示范角度 / 费曼」标记
  ④ [--score] GLM 评分（≥90 通过，70-89 缺料打回，<70 不合格）

输出：逐项指标 + 汇总判定 PASS / FAIL（附问题清单）。
退出码：0=PASS，1=FAIL（供集成/CI）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from md_rewrite_engine.core import verify as V  # noqa: E402

_SIX = ("定义", "类比", "原理", "示例", "为什么", "易错点")
_DIGIT_THRESHOLD = 0.9        # 机械对账数字覆盖率门槛
_SCORE_PASS = 90              # GLM 评分通过线（知识完整+教学可用）
_SCORE_REPAIR = 70            # 低于此不合格；70-89 缺料打回
def _feynman_min() -> int:
    """读 configs/user_prefs.yaml 的 feynman_density.general（每知识点最小示范角度），缺失/异常回退默认 2。"""
    try:
        p = os.path.join(ROOT, "configs", "user_prefs.yaml")
        with open(p, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        v = (d or {}).get("feynman_density", {}).get("general", 2)
        return int(v) if v else 2
    except Exception:  # noqa: BLE001 配置缺失回退默认，不阻断
        return 2


# ── ① 语音主体提取（对账基准）：_clean.md 抽 🎤，普通 md 用全文 ──
def extract_speech(text: str) -> str:
    """从时间轴交错 md 抽 🎤 语音行作对账基准；无 🎤 标记则返回全文。"""
    speech = re.findall(r"\[\d+:\d+\] 🎤 (.+)", text)
    return "\n".join(speech) if speech else text


def _clean_meta(text: str) -> str:
    """剥离源文本中的文件名元数据数字（日期 YYYY-MM-DD）、章节编号（1.1/1.2）、
    OCR 噪音浮点数（坐标/页码），避免机械对账误报。
    超长纯数字（视频ID/哈希）已由 core.extract_keypoints（≥10 位跳过）处理。"""
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    text = re.sub(r"\b\d{1,2}\.\d{1,2}\b", " ", text)    # 章节编号 1.1/1.2
    text = re.sub(r"\b\d{3,}\.\d{1,3}\b", " ", text)      # 长数字浮点（OCR坐标/价格）
    return text


# ── ② 6 件套完整度 ──
def _has_six_set(body: str, s: str) -> bool:
    """检查件套是否在知识点内。兼容标签变体：通俗类比/为什么重要/命令块算示例。"""
    if s == "类比":
        return bool(re.search(r"- \*\*[^\n]*类比[^\n]*\*\*", body))
    if s == "为什么":
        return bool(re.search(r"- \*\*[^\n]*为什么[^\n]*\*\*", body))
    if s == "示例":
        return bool(re.search(r"- \*\*(?:示例|命令)[^\n]*\*\*", body))
    return bool(re.search(rf"- \*\*{s}\*\*", body))


def check_six_sets(note_text: str) -> dict:
    """逐知识点查 6 件套（命令块算示例）。返回 {ok, missing: [{kp, miss}]}。"""
    kps = list(re.finditer(r"(### 知识点 ([0-9.]+) · [^\n]+\n)(.*?)(?=\n### 知识点|\n# 第|\n## 块|\n## 📖|\n## ❓|\n## 📌|\Z)", note_text, re.S))
    missing = []
    for m in kps:
        body = m.group(3)
        miss = [s for s in _SIX if not _has_six_set(body, s)]
        if miss:
            missing.append({"kp": m.group(2), "miss": miss})
    return {"ok": not missing, "missing": missing}


# ── ③ 费曼示范计数 ──
# 每条示范角度 = 一个圈数字（① ② ③ ④ ⑤）；「（复述/类比...）」是角度注解，不计独立，防双计
_FEYNMAN_MARK = re.compile(r"[①②③④⑤]")


def check_feynman(note_text: str) -> dict:
    """每知识点统计示范角度个数（①/②/③/④ 或 复述/类比/应用/挑错），≥2 达标。"""
    kps = list(re.finditer(r"(### 知识点 ([0-9.]+) · [^\n]+\n)(.*?)(?=\n### 知识点|\n# 第|\n## 块|\n## 📖|\n## ❓|\n## 📌|\Z)", note_text, re.S))
    low = []
    for m in kps:
        body = m.group(3)
        n = len(_FEYNMAN_MARK.findall(body))
        if n < _feynman_min():
            low.append({"kp": m.group(2), "n": n})
    return {"ok": not low, "low": low}


# ── 汇总判定 ──
def run(note_path: str, src_path: str = "", do_score: bool = False) -> dict:
    note = open(note_path, encoding="utf-8").read()
    src = ""
    if src_path and os.path.isfile(src_path):
        src = _clean_meta(extract_speech(open(src_path, encoding="utf-8").read()))
    elif src_path:
        # fail-closed：用户显式传了 --src 但文件不存在 → 判定 FAIL 并明示原因。
        # （曾为静默跳过报 100%——第1/2章源名错位时 PASS 因此造假，2026-09-20 修复）
        return {"note": note_path,
                "reconcile": {"coverage": 0.0, "ok": False,
                              "missing": [], "warnings": [],
                              "note": f"--src 文件不存在: {src_path}"},
                "six_sets": check_six_sets(note),
                "feynman": check_feynman(note),
                "pass": False,
                "problems": [f"原文基准文件不存在: {src_path}（机械对账无法执行，拒绝放行）"]}

    report = {"note": note_path}
    # ① 机械对账（数字硬判定）
    if src:
        r = V.reconcile(src, note)
        report["reconcile"] = {"coverage": r["coverage"], "ok": r["ok"],
                               "missing": r["missing"], "warnings": r["warnings"][:5]}
    else:
        report["reconcile"] = {"coverage": 1.0, "ok": True, "missing": [], "warnings": [],
                               "note": "无原文基准，机械对账跳过"}
    # ② 6 件套
    s6 = check_six_sets(note)
    report["six_sets"] = s6
    # ③ 费曼示范
    fy = check_feynman(note)
    report["feynman"] = fy
    # ④ GLM 评分（可选）
    if do_score:
        from md_rewrite_engine.services.llm import run_scoring  # noqa: WPS433 延迟导入
        score = run_scoring(note)
        report["score"] = score
        score_ok = score >= _SCORE_PASS
    else:
        score, score_ok = None, True
    report["score_ok"] = score_ok if score is not None else None

    # 汇总判定
    problems = []
    if not report["reconcile"]["ok"]:
        problems.append(f"机械对账 {report['reconcile']['coverage']:.0%} < 90%（缺 {report['reconcile']['missing']}）")
    if not s6["ok"]:
        problems.append(f"6 件套不全 {len(s6['missing'])} 个知识点")
    if not fy["ok"]:
        problems.append(f"费曼示范不足 {len(fy['low'])} 个知识点")
    if score is not None and not score_ok:
        problems.append(f"GLM 评分 {score} < {_SCORE_PASS}（缺料/不合格）")
    report["pass"] = not problems
    report["problems"] = problems
    return report


def _fmt(report: dict) -> str:
    lines = [f"=== 门禁检查: {os.path.basename(report['note'])} ==="]
    rc = report["reconcile"]
    lines.append(f"① 机械对账(数字): {rc['coverage']:.0%} {'✅' if rc['ok'] else '❌'} 缺失{rc['missing']}")
    s6 = report["six_sets"]
    s6_desc = "✅ 全部完整"
    if not s6["ok"]:
        detail = "; ".join(f"{x['kp']}缺{'/'.join(x['miss'])}" for x in s6["missing"][:5])
        s6_desc = f"❌ {len(s6['missing'])} 个知识点不全: {detail}"
    lines.append(f"② 6 件套: {s6_desc}")
    fy = report["feynman"]
    fy_desc = '✅ 每点≥2' if fy['ok'] else f"❌ {len(fy['low'])} 个不足"
    lines.append(f"③ 费曼示范: {fy_desc}")
    if report.get("score") is not None:
        lines.append(f"④ GLM 评分: {report['score']} {'✅' if report['score_ok'] else '❌'}")
    lines.append(f"判定: {'✅ PASS' if report['pass'] else '❌ FAIL'}")
    for p in report["problems"]:
        lines.append(f"   - {p}")
    if report["pass"]:
        lines.append("   → 通过，可交付。")
    else:
        lines.append("   → 打回：按上述问题清单针对性修补，再跑本检查（≤4 次，仍不过挂起待人工）。")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="本体主控门禁一键检查")
    p.add_argument("note", help="笔记 md 路径")
    p.add_argument("--src", default="", help="原文 md 路径（缺省仅查 6 件套/费曼）")
    p.add_argument("--score", action="store_true", help="额外跑 GLM 评分")
    args = p.parse_args(argv)
    report = run(args.note, args.src, do_score=args.score)
    print(_fmt(report))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
