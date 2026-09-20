"""providers/git_io.py — git 操作适配（B1 自动提交）。

用 subprocess 调 git；git 不可用 / 非 git 仓库 / 提交失败 → 返回 False 静默跳过，
绝不阻断主流水线（B1 降级约定）。只对单个文件 add+commit，不污染仓库其他改动。
"""
from __future__ import annotations

import os
import subprocess

_TIMEOUT = 10  # git 命令超时（秒）


def _run(args: list, cwd: str) -> bool:
    """执行 git 命令，成功返回 True；不可用/失败/超时返回 False。"""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True,
                           text=True, timeout=_TIMEOUT)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def in_git_repo(path: str) -> bool:
    """判断 path 所在目录是否在 git 仓库内。非 str/空/不存在 → False。"""
    if not isinstance(path, str) or not path:
        return False
    cwd = os.path.dirname(path) or "."
    return _run(["git", "rev-parse", "--is-inside-work-tree"], cwd)


def commit_file(path: str, message: str) -> bool:
    """对单个文件 git add + commit。

    Args:
        path: 目标文件路径。
        message: commit message。

    Returns:
        bool：提交成功；git 不可用/失败 → False（不抛异常，不阻断）。
    """
    if not isinstance(path, str) or not path:
        return False
    cwd = os.path.dirname(path) or "."
    base = os.path.basename(path)
    if not _run(["git", "add", "--", base], cwd):
        return False
    return _run(["git", "commit", "-m", message, "--", base], cwd)


def create_branch(path: str, branch_name: str) -> bool:
    """在 path 所在 git 仓库创建并切换分支（-B 覆盖已存在）。

    C2：重排前建分支（rewrite-<ts>），产出可 `git checkout master` 回滚。
    非 git 仓库/不可用 → False（不阻断）。
    """
    if not isinstance(path, str) or not path or not branch_name:
        return False
    cwd = os.path.dirname(path) or "."
    if not _run(["git", "rev-parse", "--is-inside-work-tree"], cwd):
        return False
    return _run(["git", "checkout", "-B", branch_name], cwd)


def diff_summary(path: str) -> str:
    """path 相对工作区的 git diff --stat 摘要（未提交改动）。

    供 C2 产出后 diff 预览。非 git/失败 → 空串。
    """
    if not isinstance(path, str) or not path:
        return ""
    cwd = os.path.dirname(path) or "."
    try:
        r = subprocess.run(["git", "diff", "--stat", "--", os.path.basename(path)],
                           cwd=cwd, capture_output=True, text=True, timeout=_TIMEOUT)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""
