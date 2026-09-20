# -*- coding: utf-8 -*-
"""providers/git_io + orchestrator B1 自动提交测试。"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from providers.git_io import commit_file, in_git_repo  # noqa: E402
from services.orchestrator import build_course_index  # noqa: E402


def _git_available():
    return shutil.which("git") is not None


@unittest.skipUnless(_git_available(), "需要 git")
class TestGitIO(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._repo = os.path.join(self._td, "repo")
        os.makedirs(self._repo)
        subprocess.run(["git", "init", "-q"], cwd=self._repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=self._repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self._repo, check=True)

    def test_in_git_repo_true(self):
        f = os.path.join(self._repo, "a.md")
        open(f, "w", encoding="utf-8").write("x")
        self.assertTrue(in_git_repo(f))

    def test_in_git_repo_false(self):
        plain = os.path.join(self._td, "plain")
        os.makedirs(plain)
        self.assertFalse(in_git_repo(os.path.join(plain, "a.md")))
        self.assertFalse(in_git_repo(""))
        self.assertFalse(in_git_repo(None))

    def test_commit_file(self):
        f = os.path.join(self._repo, "a.md")
        open(f, "w", encoding="utf-8").write("x")
        self.assertTrue(commit_file(f, "rewrite: a.md"))
        log = subprocess.run(["git", "log", "--oneline"], cwd=self._repo,
                             capture_output=True, text=True).stdout
        self.assertIn("rewrite: a.md", log)

    def test_commit_missing_file_false(self):
        self.assertFalse(commit_file(os.path.join(self._repo, "no.md"), "x"))

    def test_orchestrator_commits_index(self):
        """B1：build_course_index 在 git 仓库写 index 后有提交。"""
        open(os.path.join(self._repo, "01.md"), "w", encoding="utf-8").write("# A\n正文\n")
        r = build_course_index(self._repo)
        self.assertTrue(r["ok"])
        log = subprocess.run(["git", "log", "--oneline"], cwd=self._repo,
                             capture_output=True, text=True).stdout
        self.assertIn("rewrite: index.md", log)


class TestGitIOSkip(unittest.TestCase):
    def test_non_git_no_break(self):
        """非 git 目录：orchestrator 不阻断、不提交。"""
        td = tempfile.mkdtemp()
        open(os.path.join(td, "01.md"), "w", encoding="utf-8").write("# A\n正文\n")
        r = build_course_index(td)
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
