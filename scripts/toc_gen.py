# -*- coding: utf-8 -*-
"""toc_gen.py — 篇内目录（TOC）命令行工具（core/toc.py 的薄 CLI）。

用法:
  python toc_gen.py <笔记.md>          # 打印 TOC 预览（不写入）
  python toc_gen.py <笔记.md> --apply   # 生成 TOC 并插入笔记（幂等）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.toc import build_toc  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("用法: python toc_gen.py <笔记.md> [--apply]")
        return 1
    path = sys.argv[1]
    md = open(path, encoding="utf-8").read()
    new_md, headings = build_toc(md)
    if "--apply" in sys.argv:
        if not headings:
            print(f"[跳过] 无标题可生成 TOC: {path}")
            return 0
        if new_md == md:
            print(f"[已存在] TOC 已生成（幂等跳过）: {path}")
            return 0
        open(path, "w", encoding="utf-8").write(new_md)
        print(f"[OK] 已插入 TOC（{len(headings)} 个标题）: {path}")
    else:
        print(f"=== TOC 预览（{len(headings)} 个标题）===")
        for lv, t in headings:
            print(("  " * (lv - 1)) + f"[{lv}] {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
