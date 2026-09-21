"""providers/file_io.py — 读写 md / 扫描目录（外部依赖适配层）。

职责：只做文件系统适配（UTF-8、原子写、递归扫描），不藏业务逻辑。
供 services/orchestrator 调用；core 不依赖本模块（依赖倒置，core 保持纯算法）。

原子写：先写 .tmp 再 os.replace，防写入中断留下损坏文件。
"""
from __future__ import annotations

import os
import tempfile
import threading

_ENCODING = "utf-8"
# 排除的目录（隐藏/临时/构建产物）
_EXCLUDE_DIRS = frozenset({".git", ".venv", "__pycache__", "temp", "node_modules", ".idea", ".vscode"})
# 写锁：并发写同一路径时串行化 os.replace，防 Windows 文件占用冲突（PermissionError）
_WRITE_LOCK = threading.Lock()


def read_md(path: str):
    """读取 md 文件全文。

    Args:
        path: md 文件绝对路径。

    Returns:
        str 文件内容；文件不存在/非 str 路径返回 None（调用方判断）。
    """
    if not isinstance(path, str):  # None / 非 str → None（不崩）
        return None
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding=_ENCODING, errors="replace") as f:
        text = f.read()
    if text.startswith("﻿"):  # UTF-8 BOM（记事本默认），去掉防首个标题丢失
        text = text[1:]
    return text


def write_md(path: str, text: str) -> None:
    """写 md 文件（原子写：先写临时文件再 os.replace，防中断损坏）。

    父目录不存在会自动创建。
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=parent or ".", prefix=".mdrw_")
    try:
        with os.fdopen(fd, "w", encoding=_ENCODING, errors="replace") as f:
            f.write(text)
        with _WRITE_LOCK:  # 并发写同一路径：串行原子替换，防 Windows 文件占用冲突
            os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def scan_md_dir(root: str) -> list:
    """递归扫描目录下所有 .md 文件路径（排除隐藏/临时目录）。

    Args:
        root: 根目录路径。

    Returns:
        list[str]：.md 绝对路径，按文件名字典序排序（稳定）。
    """
    if not isinstance(root, str) or not os.path.isdir(root):
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)
