# -*- coding: utf-8 -*-
"""scripts/gate_check 单元测试：语音提取/6件套/费曼/判定/边界。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.gate_check import (_clean_meta, check_feynman, check_six_sets,  # noqa: E402
                                extract_speech, run)


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

    def test_no_kp(self):
        self.assertTrue(check_six_sets("无知识点纯文本")["ok"])


class TestFeynman(unittest.TestCase):
    def test_enough(self):
        t = "### 知识点 1.1 · 测试\n- **❓ 示范角度**：① ② ③\n"
        self.assertTrue(check_feynman(t)["ok"])

    def test_low(self):
        t = "### 知识点 1.1 · 测试\n- **定义**：x\n"
        r = check_feynman(t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["low"][0]["kp"], "1.1")


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
