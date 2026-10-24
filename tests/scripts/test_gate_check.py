# -*- coding: utf-8 -*-
"""scripts/gate_check 单元测试：语音提取/6件套/费曼/判定/边界。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.gate_check import (_clean_meta, check_feynman, check_six_sets,  # noqa: E402
                                extract_speech, run, strip_nonprose)


class TestStripNonprose(unittest.TestCase):
    """机器可识别的载荷不进对账基准：图 OCR 块 / 参考文献段 / URL。

    实测依据（把 9 份成品笔记的"缺失数字"逐个定位回源文区域）：图 OCR 块 26 处 +
    参考文献段 9 处，合计占全部缺失的七成。它们算成"必留硬事实"，只会逼写手
    往笔记里塞读者用不上的数字。
    """

    def test_drops_a_figure_ocr_block(self):
        t = ("正文 3000 在这里。\n\n## 插图笔记\n\n## 图片内容（OCR）\n\n"
             "1000\n800\n600\n\n## GLM 画面理解\n\n这是一张折线图，纵轴到 1000。\n\n"
             "## 下一节\n\n正文 5000 还在。\n")
        out = strip_nonprose(t)
        self.assertNotIn("1000", out)
        self.assertNotIn("插图笔记", out)
        self.assertIn("3000", out)      # 块之前的正文留下
        self.assertIn("5000", out)      # 块之后的正文留下
        self.assertIn("下一节", out)

    def test_drops_a_reference_section(self):
        t = ("正文 3000。\n\n## References\n\n[1] X. Journal, 2021(19): 183-185.\n\n"
             "## 附录\n\n5000 还在。\n")
        out = strip_nonprose(t)
        self.assertNotIn("183", out)
        self.assertIn("3000", out)
        self.assertIn("5000", out)

    def test_drops_urls(self):
        out = strip_nonprose("见 http://data.cma.cn/Market/Detail/code/A.0012.0001/type/1.htm 正文 3000")
        self.assertNotIn("0012", out)
        self.assertIn("3000", out)

    def test_a_plain_note_is_untouched(self):
        t = "# 标题\n\n正文 3000，另有 5000。\n"
        self.assertEqual(strip_nonprose(t), t)


class TestCleanMeta(unittest.TestCase):
    def test_removes_date(self):
        self.assertNotIn("2026", _clean_meta("标题 2026-06-30 内容"))
        self.assertIn("内容", _clean_meta("标题 2026-06-30 内容"))

    def test_keeps_content_digits(self):
        self.assertIn("3000", _clean_meta("端口 3000"))


class TestExtractSpeech(unittest.TestCase):
    def test_clean_md_extract_speech(self):
        t = "# 标题\n\n## 转写+画面\n\n[00:00] 🎤 第一句。\n🖼 [00:00]\n碎片\n[00:05] 🎤 第二句。\n"
        self.assertEqual(extract_speech(t), "第一句。\n第二句。")

    def test_plain_md_full_text(self):
        t = "# 标题\n\n普通正文 3000。\n"
        self.assertEqual(extract_speech(t), t)

    def test_empty(self):
        self.assertEqual(extract_speech(""), "")


class TestSixSets(unittest.TestCase):
    KP_OK = ("### 知识点 1.1 · 测试\n"
             "- **定义**：x\n- **通俗类比**：y\n- **原理**：z\n"
             "- **示例（事实命令）**：cmd\n- **为什么重要**：w\n- **易错点**：e\n")

    def test_complete(self):
        r = check_six_sets(self.KP_OK)
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])

    def test_missing_sets(self):
        t = "### 知识点 1.1 · 测试\n- **定义**：x\n- **易错点**：e\n"
        r = check_six_sets(t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["missing"][0]["kp"], "1.1")
        self.assertIn("类比", r["missing"][0]["miss"])

    def test_command_block_as_example(self):
        t = "### 知识点 1.1 · 测试\n- **定义**：x\n- **命令（原样保留）**：\n```bash\nwsl --install\n```\n"
        r = check_six_sets(t)
        # 命令块算示例，不应报缺示例
        self.assertNotIn("示例", r["missing"][0]["miss"] if r["missing"] else [])

    def test_no_kp_fails_instead_of_passing_vacuously(self):
        # 空集不等于没问题：切不到知识点就无从校验，不许报"✅ 全部完整"
        r = check_six_sets("无知识点纯文本")
        self.assertFalse(r["ok"])
        self.assertIn("切不到知识点", r["reason"])


class TestFeynman(unittest.TestCase):
    def test_enough(self):
        t = "### 知识点 1.1 · 测试\n- **❓ 示范角度**：① ② ③\n"
        self.assertTrue(check_feynman(t)["ok"])

    def test_low(self):
        t = "### 知识点 1.1 · 测试\n- **定义**：x\n"
        r = check_feynman(t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["low"][0]["kp"], "1.1")

    def test_no_kp_fails_instead_of_passing_vacuously(self):
        r = check_feynman("无知识点纯文本")
        self.assertFalse(r["ok"])
        self.assertIn("切不到知识点", r["reason"])

    def test_circles_outside_the_demo_block_do_not_count(self):
        # B-9：旧实现数整个知识点正文的圈数字，而「易错点」几乎每点都用 ①②③④ 列举，
        # 于是整块示范角度被删掉也照样判过。圈数字只有挂在「❓ 示范角度」下面才算。
        t = ("### 知识点 1.1 · 测试\n"
             "- **定义**：x\n- **易错点**：① 别这样 ② 别那样 ③ 也别 ④ 更别\n")
        r = check_feynman(t)
        self.assertFalse(r["ok"], "易错点里的圈数字不能冒充示范角度")
        self.assertEqual(r["low"][0]["n"], 0)

    def test_block_stops_at_the_next_six_set_item(self):
        # 示范角度块到下一个六件套项为止：后面的圈数字不算这个点的。
        t = ("### 知识点 1.1 · 测试\n"
             "- **❓ 示范角度**：\n  ① a\n  ② b\n"
             "- **易错点**：③ 别这样\n")
        r = check_feynman(t)
        self.assertTrue(r["ok"])
        # 同一个知识点 1.2 只有示范角度标签、没有条目 → 仍算不足
        t2 = t + "### 知识点 1.2 · 另一个\n- **❓ 示范角度**：\n"
        self.assertFalse(check_feynman(t2)["ok"])

    def test_feynman_label_variant_is_accepted(self):
        # note_style_spec.yaml 里这一项叫「❓ 费曼思考题」，交付物实际写「❓ 示范角度」。
        # 两种都得认，否则按规范写的会被误判。
        for label in ("❓ 示范角度", "❓ 费曼思考题"):
            t = "### 知识点 1.1 · 测试\n- **%s**：\n  ① a\n  ② b\n" % label
            self.assertTrue(check_feynman(t)["ok"], label)

    def test_label_mentioned_in_prose_does_not_count(self):
        # 导语里解释六件套时会提到这个词，那不是示范角度块。
        t = ("### 知识点 1.1 · 测试\n"
             "- **怎么读**：第七项是「❓ 示范角度」，只给线索\n"
             "- **易错点**：① ② ③ ④\n")
        self.assertFalse(check_feynman(t)["ok"])


class TestRun(unittest.TestCase):
    def _note(self, extra=""):
        return ("### 知识点 1.1 · 测试\n"
                "- **定义**：x\n- **通俗类比**：y\n- **原理**：z\n"
                "- **示例**：cmd 3000\n- **为什么重要**：w\n- **易错点**：e\n"
                "- **❓ 示范角度**：① ② ③\n" + extra)

    def test_pass_with_src(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            sp = os.path.join(d, "s.md")
            open(np, "w", encoding="utf-8").write(self._note())
            open(sp, "w", encoding="utf-8").write("测试 3000 内容")
            r = run(np, sp)
            self.assertTrue(r["pass"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_axis_ticks_in_a_figure_block_are_not_required(self):
        """图里的刻度不算"必留硬事实"：源文有、笔记没写，不该判缺（B-6）。"""
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            sp = os.path.join(d, "s.md")
            open(np, "w", encoding="utf-8").write(self._note())
            open(sp, "w", encoding="utf-8").write(
                "正文 3000 内容\n\n## 插图笔记\n\n## 图片内容（OCR）\n\n6350\n6250\n6150\n")
            r = run(np, sp)
            self.assertEqual(r["reconcile"]["missing"], [])
            self.assertTrue(r["reconcile"]["ok"])
            self.assertTrue(r["pass"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_a_reference_page_number_is_not_required(self):
        """文献页码同理：清样里的 183-185 不是教学内容（B-6）。"""
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            sp = os.path.join(d, "s.md")
            open(np, "w", encoding="utf-8").write(self._note())
            open(sp, "w", encoding="utf-8").write(
                "正文 3000 内容\n\n## References\n\n[1] X. Journal, 2021(19): 183-185.\n")
            r = run(np, sp)
            self.assertEqual(r["reconcile"]["missing"], [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_a_body_number_still_required(self):
        """反向锁：正文里的数字照旧必须保留——别把这条改动读成"数字都不查了"。"""
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            sp = os.path.join(d, "s.md")
            open(np, "w", encoding="utf-8").write(self._note())
            open(sp, "w", encoding="utf-8").write("正文 3000 与 7777 两个数字。\n")
            r = run(np, sp)
            self.assertIn("7777", r["reconcile"]["missing"])
            self.assertFalse(r["reconcile"]["ok"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_fail_missing_sixset(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            open(np, "w", encoding="utf-8").write(
                "### 知识点 1.1 · 测试\n- **定义**：x\n")
            r = run(np)
            self.assertFalse(r["pass"])
            self.assertTrue(any("6 件套" in p for p in r["problems"]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_no_src_reconcile_ok(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            open(np, "w", encoding="utf-8").write(self._note())
            rr = run(np, "")  # 无原文 → 对账跳过 ok
            self.assertTrue(rr["reconcile"]["ok"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_variants_warning_not_blocking(self):
        # 术语变体是 warning 级：有变体不翻 PASS 判定（Task-06）
        # 构造贴近真实：笔记保留源措辞、仅 1 字之差（调度器→掉度器）
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            sp = os.path.join(d, "s.md")
            np = os.path.join(d, "n.md")
            src = ("这是一段讲解调度器原理的教程文本。\n"
                   "调度器负责请求的排队，队列容量 100，超时 200 毫秒。\n")
            note = ("# 标题\n\n### 知识点 1.1 · 调度器\n\n"
                    "这是一段讲解掉度器原理的教程文本。\n"
                    "调度器负责请求的排队，队列容量 100，超时 200 毫秒。\n"
                    "- **定义**：x\n- **通俗类比**：x\n- **原理**：x\n"
                    "- **示例**：x\n- **为什么重要**：x\n- **易错点**：x\n"
                    # 这两个圈数字必须挂在「❓ 示范角度」标签下：check_feynman 只在该块内
                    # 计数，光秃秃放在知识点末尾会被判"没有示范角度"（B-9）。
                    "- **❓ 示范角度**：\n"
                    "  ①（复述）a\n  ②（应用）b\n")
            open(sp, "w", encoding="utf-8").write(src)
            open(np, "w", encoding="utf-8").write(note)
            rr = run(np, sp)
            self.assertTrue(rr["pass"], f"变体不应翻判定: {rr['problems']}")
            self.assertGreaterEqual(len(rr["variants"]), 1)
            self.assertEqual(rr["variants"][0]["distance"], 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_variants_absent_when_clean(self):
        # 原样保留（无变体）→ variants 空
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            sp = os.path.join(d, "s.md")
            np = os.path.join(d, "n.md")
            src = "这是一段讲解调度器原理的教程文本。"
            note = ("# 标题\n\n## 第一节\n\n调度器原理讲解。\n"
                    "- **定义**：x\n- **通俗类比**：x\n- **原理**：x\n"
                    "- **示例**：x\n- **为什么重要**：x\n- **易错点**：x\n"
                    "①（复述）a\n②（应用）b\n")
            open(sp, "w", encoding="utf-8").write(src)
            open(np, "w", encoding="utf-8").write(note)
            rr = run(np, sp)
            self.assertEqual(rr["variants"], [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_expansion_none_without_src(self):
        # 无原文基准 → expansion=None，不进 problems
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            open(np, "w", encoding="utf-8").write(self._note())
            rr = run(np, "")
            self.assertIsNone(rr["expansion"])
            self.assertTrue(rr["pass"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_expansion_fail_blocks_pass(self):
        # 薄笔记 vs 厚源：膨胀率撞绝对红线 → FAIL 且 problems 含丰富度（Task-02）
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            sp = os.path.join(d, "s.md")
            np = os.path.join(d, "n.md")
            open(sp, "w", encoding="utf-8").write("详细推导内容。" * 200)
            open(np, "w", encoding="utf-8").write(self._note("薄。"))
            rr = run(np, sp)
            self.assertFalse(rr["pass"])
            self.assertIsNotNone(rr["expansion"])
            self.assertFalse(rr["expansion"]["ok"])
            self.assertTrue(any("丰富度" in p for p in rr["problems"]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_expansion_pass_thick_note(self):
        # 笔记扩写充足（≥80%）→ 直过不豁免
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            sp = os.path.join(d, "s.md")
            np = os.path.join(d, "n.md")
            open(sp, "w", encoding="utf-8").write("核心讲解内容。" * 100)
            open(np, "w", encoding="utf-8").write(self._note("扩写讲解。" * 130))
            rr = run(np, sp)
            self.assertTrue(rr["expansion"]["ok"])
            self.assertFalse(rr["expansion"]["exempt"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_fail_closed_schema_includes_expansion(self):
        # --src 不存在 → fail-closed FAIL；schema 与正常报告一致（expansion/score_ok 键）
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            np = os.path.join(d, "n.md")
            sp = os.path.join(d, "s.md")
            open(np, "w", encoding="utf-8").write(self._note())
            open(sp, "w", encoding="utf-8").write("测试 3000 内容")
            r_bad = run(np, os.path.join(d, "ghost.md"))
            r_ok = run(np, sp)
            self.assertFalse(r_bad["pass"])
            self.assertIsNone(r_bad["expansion"])
            self.assertIsNone(r_bad["score_ok"])
            self.assertEqual(sorted(r_bad.keys()), sorted(r_ok.keys()))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
