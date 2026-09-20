# -*- coding: utf-8 -*-
"""providers/file_io 单元测试：读写 / 原子写 / 扫描。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from providers.file_io import read_md, scan_md_dir, write_md  # noqa: E402


class TestFileIO(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp()

    def test_rw_chinese(self):
        p = os.path.join(self._td, "中文 笔记.md")
        write_md(p, "# 你好\n\n中文内容。\n")
        self.assertEqual(read_md(p), "# 你好\n\n中文内容。\n")

    def test_atomic_no_tmp(self):
        p = os.path.join(self._td, "a.md")
        write_md(p, "第一版")
        write_md(p, "第二版")
        self.assertFalse(any(f.endswith(".tmp") for f in os.listdir(self._td)))
        self.assertEqual(read_md(p), "第二版")

    def test_read_missing(self):
        self.assertIsNone(read_md(os.path.join(self._td, "没有.md")))

    def test_scan(self):
        os.makedirs(os.path.join(self._td, "sub"))
        write_md(os.path.join(self._td, "a.md"), "a")
        write_md(os.path.join(self._td, "sub", "b.md"), "b")
        found = scan_md_dir(self._td)
        self.assertEqual(len(found), 2)

    def test_scan_missing_dir(self):
        self.assertEqual(scan_md_dir(os.path.join(self._td, "nope")), [])


if __name__ == "__main__":
    unittest.main()
