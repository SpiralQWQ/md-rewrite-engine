# -*- coding: utf-8 -*-
"""scripts/filters/ebook_source_filter.py — MinerU 图文书源过滤（v0.4.5 第 0 步扩展）。

用途：MinerU 解析的「图文型电子书」md（full_embedded.md）会把每张插图转成三段记录：
    ## 插图笔记：<64位哈希>
    ## 图片内容（OCR）
    ## GLM 画面理解
这些块会破坏门禁：
  ① 污染机械对账——OCR 碎片数字（0.1 / 0000 / 001）被 extract_keypoints 当作
     "必须保留的关键点"（实测一本图文书：全文 3210 个关键点里 2946 个来自图片块），
     笔记永远对不上 → 覆盖率误判 → 门禁 FAIL；
  ② 虚高膨胀率分母——图片块占源 68%，笔记膨胀率被误判成"偷工压缩"（100% 掉到 31%）。

本工具生成「正文版」对账基准（clean_only.md）供 gate_check 使用；
原始 full_embedded.md 不动——照旧外置到 源数据/转写.md 保留全量溯源。

用法：
    python -m scripts.filters.ebook_source_filter --src full_embedded.md --out clean_only.md
    python -m scripts.filters.ebook_source_filter --src ... --out ... --keep-glm

规则（MinerU 图文书通用，不依赖具体书目）：
    块首 ## 插图笔记：        → 剔除（哈希标题，纯噪音）
    块首 ## 图片内容（OCR）    → 剔除（多栏 OCR 乱序碎片）
    块首 ## GLM 画面理解       → 默认剔除；--keep-glm 时保留（图的文字描述，可作参考）
    其他所有块（各级标题/正文/代码块）→ 保留

防呆（fail-closed）：src 不存在 / 空文件 / 过滤后为空 → 报错退出码 2，不产出残缺基准。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# 图片块三类（MinerU 图文书产物结构）
_IMG_HASH_HEAD = "## 插图笔记："
_IMG_OCR_HEAD = "## 图片内容（OCR）"
_IMG_GLM_HEAD = "## GLM 画面理解"


def split_blocks(text: str) -> list:
    """按 '## ' 标题切块（标题行随块保留）；首块为文档标题+导语。"""
    return re.split(r"(?m)^(?=## )", text)


def filter_ebook_source(text: str, keep_glm: bool = False) -> tuple:
    """剔除图片三连块，返回 (正文, 统计)。keep_glm=True 时保留 GLM 画面理解块。"""
    kept, dropped = [], {"hash": 0, "ocr": 0, "glm": 0}
    for blk in split_blocks(text):
        head = blk.split("\n", 1)[0]
        if head.startswith(_IMG_HASH_HEAD):
            dropped["hash"] += 1
            continue
        if head.startswith(_IMG_OCR_HEAD):
            dropped["ocr"] += 1
            continue
        if head.startswith(_IMG_GLM_HEAD):
            dropped["glm"] += 1
            if keep_glm:
                kept.append(blk)
            continue
        kept.append(blk)
    return "".join(kept), dropped


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MinerU 图文书源过滤：提取正文作为对账基准")
    parser.add_argument("--src", required=True, help="full_embedded.md 路径")
    parser.add_argument("--out", required=True, help="输出 clean_only.md 路径")
    parser.add_argument("--keep-glm", action="store_true",
                        help="保留 GLM 画面理解块（默认剔除）")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.src):
        print(f"[ERROR] src not found: {args.src}")
        return 2
    try:
        with open(args.src, encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        print(f"[ERROR] src is not valid UTF-8: {args.src}")
        return 2
    if not text.strip():
        print(f"[ERROR] src is empty: {args.src}")
        return 2

    out_text, dropped = filter_ebook_source(text, keep_glm=args.keep_glm)
    if not out_text.strip():
        print("[ERROR] filtered result is empty (input was all image blocks?)")
        return 2

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(out_text)

    print(f"[ok] {args.src}")
    print(f"     -> {args.out}")
    print(f"     dropped: hash={dropped['hash']} ocr={dropped['ocr']} "
          f"glm={dropped['glm']}{' (kept)' if args.keep_glm else ''}")
    print(f"     chars: {len(text):,} -> {len(out_text):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
