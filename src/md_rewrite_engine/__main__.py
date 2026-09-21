#!/usr/bin/env python3
"""cli.py — md-rewrite-engine 命令行入口（薄层：只解析参数 → 调 orchestrator）。

用法:
    python cli.py <清洗后md路径> [--output 输出.md] [--max-chars 8000]
                  [--overlap 200] [--glossary 术语表] [--spec configs/note_style_spec.yaml]
                  [--retries 1]

防呆：无参数/缺 input → 帮助；文件不存在/空内容 → 明确报错（退出码非 0）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from md_rewrite_engine.services.orchestrator import (build_concepts, build_course_index, process,  # noqa: E402
                                   search_course, validate_course_links)


def _load_spec(path: str):
    """读 note_style_spec.yaml → dict。文件缺失返回 None（用通用要求）。"""
    if not path or not os.path.isfile(path):
        return None
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 规范缺失不阻断
        return None


def _default_spec_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs", "note_style_spec.yaml")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="清洗后 md → AI 友好 md（环节1）")
    p.add_argument("input", nargs="?", help="清洗后 md 文件路径（与 --index 二选一）")
    p.add_argument("--output", default="", help="输出 md 路径（默认不写文件，仅打印结果摘要）")
    p.add_argument("--index", default="", help="课程目录：生成总索引 index.md（D1，替代重排流水线）")
    p.add_argument("--validate-links", default="", help="课程目录：校验笔记 [[链接]] 悬空（D2）")
    p.add_argument("--concepts", default="", help="课程目录：生成概念页（D7）")
    p.add_argument("--search", default="", help="关键词：在课程目录中检索（input 作为课程目录，D8）")
    p.add_argument("--max-chars", type=int, default=8000, help="每块最大字符（默认 8000）")
    p.add_argument("--overlap", type=int, default=200, help="块间重叠字符（默认 200）")
    p.add_argument("--glossary", default="", help="术语表文本（注入重排）")
    p.add_argument("--spec", default="", help="note_style_spec.yaml 路径（默认 configs/note_style_spec.yaml）")
    p.add_argument("--retries", type=int, default=1, help="单块验证不过的重排重试次数（默认 1）")
    p.add_argument("--json", action="store_true", help="输出 JSON 结果（供其他工具集成）")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 防呆：参数合法性由 argparse 兜底（type=int 拒绝非法数字）；缺 input 自动帮助
    if args.max_chars < 100:
        parser.error("--max-chars 必须 ≥100")
    if args.overlap < 0:
        parser.error("--overlap 不能为负")
    if args.retries < 0:
        parser.error("--retries 不能为负")

    # --index 模式：生成课程总索引（D1，不跑重排流水线）
    if args.index:
        if args.input:
            parser.error("--index 与输入文件不能同时使用")
        r = build_course_index(args.index, args.output)
        if args.json:
            summary = {k: v for k, v in r.items() if k != "output"}
            print(json.dumps(summary, ensure_ascii=False))
        else:
            print(f"课程目录: {args.index}")
            print(f"笔记数: {r.get('notes', 0)}")
            if r.get("ok"):
                print(f"已生成索引: {r.get('index_path')}")
            if r.get("error"):
                print(f"错误: {r['error']}")
        return 0 if r.get("ok") else 1

    # --validate-links 模式：校验课程笔记链接（D2）
    if args.validate_links:
        if args.input or args.index:
            parser.error("--validate-links 与输入/--index 不能同时使用")
        r = validate_course_links(args.validate_links)
        if args.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            print(f"课程目录: {args.validate_links}")
            print(f"已校验笔记: {r.get('checked', 0)}")
            print(f"悬空链接: {r.get('broken_total', 0)}")
            for b in r.get("broken", []):
                print(f"  {b['file']}: {', '.join(b['links'])}")
            rel_miss = r.get("relation_missing_total", 0)
            rel_brk = r.get("relation_broken_total", 0)
            print(f"关联字段缺失: {rel_miss} | 悬空: {rel_brk}")
            for ri in r.get("relation_issues", [])[:5]:
                if ri.get("broken"):
                    print(f"  [{ri['file']}] 悬空: {', '.join(ri['broken'])}")
            print(f"示例缺出处: {r.get('citation_missing_total', 0)}")
            conf = r.get("conf_issues_total", 0)
            print(f"置信度异常(缺失/非法): {conf}")
            for ci in r.get("conf_issues", [])[:5]:
                print(f"  [{ci['file']}] {', '.join(ci['issues'])}")
            lowc = r.get("low_conf", [])
            if lowc:
                print(f"低置信抽查: {', '.join(lowc)}")
            if r.get("error"):
                print(f"错误: {r['error']}")
        return 0 if r.get("ok") else 1

    # --concepts 模式：生成概念页（D7）
    if args.concepts:
        if args.input or args.index or args.validate_links:
            parser.error("--concepts 与其他模式不能同时使用")
        r = build_concepts(args.concepts)
        if args.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            print(f"课程目录: {args.concepts}")
            print(f"概念页: {r.get('concepts', 0)}")
            if r.get("pages_dir"):
                print(f"输出目录: {r.get('pages_dir')}")
            for pg in r.get("pages", [])[:10]:
                print(f"  {pg['name']} → {pg['file']}")
            if r.get("error"):
                print(f"错误: {r['error']}")
        return 0 if r.get("ok") else 1

    # --search 模式：课程目录词法检索（D8，input 作为课程目录）
    if args.search:
        if args.index or args.validate_links or args.concepts:
            parser.error("--search 与其他模式不能同时使用")
        if not args.input:
            parser.error("--search 需要 input 作为课程目录")
        r = search_course(args.input, args.search)
        if args.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            print(f"检索: {r.get('query')} @ {args.input}")
            for res in r.get("results", []):
                print(f"  {res['file']} (命中 {res['score']}):")
                for h in res["hits"][:2]:
                    print(f"    - {h}")
            if r.get("error"):
                print(f"错误: {r['error']}")
        return 0 if r.get("ok") else 1

    if not args.input:
        parser.error("需要输入文件路径或 --index 课程目录")

    spec_path = args.spec or _default_spec_path()
    spec = _load_spec(spec_path)

    result = process(
        args.input,
        output_path=args.output,
        spec=spec,
        glossary=args.glossary,
        max_chars=args.max_chars,
        overlap_chars=args.overlap,
        max_rewrite_retries=args.retries,
    )

    if args.json:
        # 只输出可序列化字段（不输出超长 output 全文）
        summary = {k: v for k, v in result.items() if k != "output"}
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"输入: {args.input}")
        print(f"编译单元: {result.get('units', 0)}")
        print(f"结果: {'✅ 通过' if result.get('ok') else '⚠️ 存在问题'}")
        if result.get("issues"):
            for i in result.get("issues", [])[:10]:
                print(f"  - {i}")
        if result.get("error"):
            print(f"错误: {result['error']}")
        if result.get("output_path"):
            print(f"已写入: {result['output_path']}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
