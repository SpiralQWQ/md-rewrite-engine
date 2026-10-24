# -*- coding: utf-8 -*-
"""core/toc 单元测试：篇内目录生成（提取/幂等/主标题排除/边界）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from md_rewrite_engine.core.toc import (  # noqa: E402
    build_toc, extract_headings, render_toc, strip_toc,
)


class TestToc(unittest.TestCase):
    SAMPLE = (
        "# 主标题\n"
        "## 第一节\n"
        "正文内容。\n"
        "### 知识点 A\n"
        "### 知识点 B\n"
        "## 第二节\n"
        "### 知识点 C\n"
    )

    def test_extract_headings_levels(self):
        hs = extract_headings(self.SAMPLE)
        self.assertEqual(hs, [(1, "主标题"), (2, "第一节"), (3, "知识点 A"),
                               (3, "知识点 B"), (2, "第二节"), (3, "知识点 C")])

    def test_build_skips_main_title(self):
        # 文档主标题（第一个 H1）不列入 TOC
        new, hs = build_toc(self.SAMPLE)
        self.assertNotIn("主标题", new.split("## 📑 本篇目录")[1].splitlines()[1] if "本篇目录" in new else "")
        self.assertEqual(hs[0], (2, "第一节"))

    def test_build_inserts_after_main_title(self):
        new, hs = build_toc(self.SAMPLE)
        self.assertIn("## 📑 本篇目录", new)
        # TOC 在主标题之后、第一节之前
        pos_title = new.index("# 主标题")
        pos_toc = new.index("本篇目录")
        pos_sec = new.index("## 第一节")
        self.assertTrue(pos_title < pos_toc < pos_sec)

    def test_build_toc_has_links(self):
        new, _ = build_toc(self.SAMPLE)
        self.assertIn("- [第一节](#第一节)", new)
        self.assertIn("- [知识点 A](#知识点-a)", new)

    def test_anchor_keeps_one_hyphen_per_space(self):
        """带标点的标题：GitHub 逐空格替换、不合并连续空白。

        「知识点 2.1 · 标题」里 `·` 被删掉后**两侧各剩一个空格**，
        所以锚点必须有两个连字符。旧的 `re.sub(r"\\s+", "-")` 会合并成一个，
        导致 8 份笔记的 88 个目录链接全部点不动（回灌清单 B-8）。
        """
        toc = render_toc([(2, "知识点 2.1 · IP 地址与子网掩码：网段怎么判断")])
        self.assertIn("(#知识点-21--ip-地址与子网掩码网段怎么判断)", toc)

    def test_anchor_of_a_plain_title_is_unchanged(self):
        # 没标点的标题两套规则一致——这条锁住"别为了改 B-8 把普通标题改坏"。
        toc = render_toc([(2, "知识点 A")])
        self.assertIn("(#知识点-a)", toc)

    def test_build_idempotent(self):
        once, _ = build_toc(self.SAMPLE)
        twice, _ = build_toc(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count("本篇目录"), 1)

    def test_build_frontmatter_insert_after_fm(self):
        md = "---\ntitle: 测试\n---\n\n# 主\n## 内容\n"
        new, _ = build_toc(md)
        # frontmatter 闭合 --- 后是主标题，TOC 在两者之后
        self.assertIn("---\n\n# 主\n## 📑 本篇目录", new)

    def test_build_empty_input(self):
        self.assertEqual(build_toc(""), ("", []))
        self.assertEqual(build_toc(None), (None, []))
        self.assertEqual(build_toc("   \n "), ("   \n ", []))

    def test_build_no_headings(self):
        new, hs = build_toc("纯正文，没有标题。\n\n再来一行。")
        self.assertEqual(hs, [])
        self.assertEqual(new, "纯正文，没有标题。\n\n再来一行。")

    def test_extract_skip_codeblock(self):
        md = "# 主\n\n```\n# 代码块里的标题不算\n```\n\n## 真标题\n"
        hs = extract_headings(md)
        self.assertEqual(hs, [(1, "主"), (2, "真标题")])

    def test_render_no_headings_empty(self):
        self.assertEqual(render_toc([]), "")

    def test_build_replaces_existing_toc(self):
        # 已有 TOC 的笔记：重新生成不产生两个 TOC
        first, _ = build_toc(self.SAMPLE)
        second, hs = build_toc(first)
        self.assertEqual(second.count("本篇目录"), 1)
        self.assertTrue(hs)

    def test_refresh_rebuilds_a_stale_toc(self):
        # B-5：标题改过之后，默认不刷新会让目录停在旧标题集（锚点全部失效），
        # refresh=True 才把目录换成按当前标题算出来的。
        first, _ = build_toc(self.SAMPLE)
        changed = first.replace("## 第二节", "## 第二节（改名）")
        stale, _ = build_toc(changed)
        self.assertIn("- [第二节](#第二节)", stale)
        self.assertNotIn("- [第二节（改名）]", stale)

        fresh, hs = build_toc(changed, refresh=True)
        self.assertEqual(fresh.count("本篇目录"), 1)
        self.assertIn("- [第二节（改名）](#第二节改名)", fresh)
        self.assertNotIn("- [第二节](#第二节)", fresh)
        self.assertEqual(hs[0], (2, "第一节"))

    def test_refresh_is_idempotent(self):
        once, _ = build_toc(self.SAMPLE, refresh=True)
        twice, _ = build_toc(once, refresh=True)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count("本篇目录"), 1)

    def test_strip_toc_stops_before_following_content(self):
        # 目录块紧跟引言 blockquote：剥目录只许剥目录，别把引言一起吃掉
        md = ("# 主\n\n## 📑 本篇目录\n\n- [第一节](#第一节)\n\n---\n\n"
              "> 引言：别删我。\n\n## 第一节\n")
        out = strip_toc(md)
        self.assertNotIn("本篇目录", out)
        self.assertIn("> 引言：别删我。", out)
        self.assertIn("## 第一节", out)

    def test_build_bom_frontmatter_position(self):
        text = "﻿---\ntitle: 测试\n---\n\n# 主标题\n\n## 第一节\n\n正文。\n"
        new, hs = build_toc(text)
        self.assertIn("## 📑 本篇目录", new)
        pos_fm = new.index("title:")
        pos_toc = new.index("本篇目录")
        self.assertLess(pos_fm, pos_toc, "TOC 被插到 frontmatter 之前（BOM 致错位）")

    def test_build_bom_idempotent(self):
        text = ("﻿---\ntitle: 测试\n---\n\n# 主标题\n\n## 📑 本篇目录\n\n"
                "- [第一节](#第一节)\n\n## 第一节\n")
        new, _ = build_toc(text)
        self.assertEqual(new.count("本篇目录"), 1)

    def test_parse_frontmatter_end_bom(self):
        from md_rewrite_engine.core.toc import parse_frontmatter_end
        text = "﻿---\ntitle: x\n---\n\n正文"
        self.assertEqual(parse_frontmatter_end(text), 3)


if __name__ == "__main__":
    unittest.main()
