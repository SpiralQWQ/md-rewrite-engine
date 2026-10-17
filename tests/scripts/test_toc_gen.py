# -*- coding: utf-8 -*-
"""scripts/toc_gen 的命令行契约：按文档那样直接跑就得能跑起来。

src 布局下包在 `<repo>/src/md_rewrite_engine/`，脚本只把 `<repo>` 挂上 sys.path
是导不到的。此前本脚本就是这样：文档写着 `python scripts/toc_gen.py <笔记.md> --apply`，
照做却 ModuleNotFoundError —— 只有调用方额外给了 PYTHONPATH（包已安装、或上层编排器
设了）才活。一个跑不起来的 CLI 会把"目录没刷新"伪装成"工具没输出"。
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "scripts", "toc_gen.py")


class TestTocGenCli(unittest.TestCase):
    def _run(self, content, *args):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "n.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)      # 不许靠外部替它挂 sys.path
        env["PYTHONIOENCODING"] = "utf-8"
        # cwd 换到临时目录：python 只会自动把 *脚本所在目录* 加进 sys.path，
        # 所以这条测试真的在验"脚本自己有没有把 <repo>/src 挂上"。
        # encoding 必须写死：子进程被强制按 UTF-8 输出，而 Windows 控制台下
        # subprocess 默认按本机 ANSI 码页（cp936）解，reader 线程会 UnicodeDecodeError、
        # stdout 直接变成 None。同仓库其他测试与调用方都是这么写的。
        proc = subprocess.run([sys.executable, SCRIPT, path] + list(args),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, cwd=d)
        with open(path, encoding="utf-8") as f:
            return proc, f.read()

    def test_apply_works_without_an_external_pythonpath(self):
        proc, text = self._run("# 主标题\n\n## 甲节\n\n正文。\n", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("## 📑 本篇目录", text)
        self.assertIn("- [甲节](#甲节)", text)

    def test_apply_refreshes_a_stale_toc(self):
        # 先造一份带旧目录的笔记，再跑 --apply：目录必须跟着新标题走
        stale = ("# 主标题\n\n## 📑 本篇目录\n\n- [旧节](#旧节)\n\n---\n\n"
                 "> 引言：别删我。\n\n## 甲节\n\n正文。\n")
        proc, text = self._run(stale, "--apply")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("- [甲节](#甲节)", text)
        self.assertNotIn("- [旧节](#旧节)", text)
        self.assertEqual(text.count("本篇目录"), 1)
        self.assertIn("引言：别删我。", text)

    def test_without_apply_it_only_previews(self):
        original = "# 主标题\n\n## 甲节\n\n正文。\n"
        proc, text = self._run(original)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TOC 预览", proc.stdout)
        self.assertEqual(text, original)      # 不写盘


if __name__ == "__main__":
    unittest.main()
