# -*- coding: utf-8 -*-
"""toc_gen.py — 篇内目录（TOC）命令行工具（core/toc.py 的薄 CLI）。

用法:
  python toc_gen.py <笔记.md>          # 打印 TOC 预览（不写入）
  python toc_gen.py <笔记.md> --apply   # 生成/刷新 TOC 并写回笔记

--apply 是**重建**：已有目录会被换成按当前标题算出来的新目录（标题改过之后
必须如此，否则目录停在旧标题集、锚点全失效——回灌清单 B-5）。标题没变时
重建结果与原文一致，写回等同于不写。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# src 布局：包在 <repo>/src/md_rewrite_engine/，只挂 <repo> 是导不到的
# （2026-10-15 修：此前按本文件文档那样直接 `python scripts/toc_gen.py x.md`
#   会 ModuleNotFoundError，只有调用方额外给 PYTHONPATH 才活）。
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from md_rewrite_engine.core.toc import build_toc  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("用法: python toc_gen.py <笔记.md> [--apply]")
        return 1
    path = sys.argv[1]
    md = open(path, encoding="utf-8").read()
    apply_ = "--apply" in sys.argv
    new_md, headings = build_toc(md, refresh=apply_)
    if apply_:
        if not headings:
            print(f"[跳过] 无标题可生成 TOC: {path}")
            return 0
        if new_md == md:
            print(f"[OK] TOC 已是最新（{len(headings)} 个标题）: {path}")
            return 0
        open(path, "w", encoding="utf-8").write(new_md)
        print(f"[OK] 已生成/刷新 TOC（{len(headings)} 个标题）: {path}")
    else:
        print(f"=== TOC 预览（{len(headings)} 个标题）===")
        for lv, t in headings:
            print(("  " * (lv - 1)) + f"[{lv}] {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
