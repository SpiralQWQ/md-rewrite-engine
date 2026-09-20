# -*- coding: utf-8 -*-
"""core/rewrite 单元测试：滚动编译调度 / 摘要贯穿 / 边界合并。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.rewrite import rolling_compile  # noqa: E402


def _fake(text, prev_summary):
    """返回 (rewritten, summary, merge)。含 'MERGE' 则请求合并。"""
    first = text.strip().splitlines()[0][:8]
    return (f"REW:{first}", f"{prev_summary}|{first}", "MERGE" in text)


class TestRolling(unittest.TestCase):
    def _chunks(self, n):
        return [{"text": f"块{i}内容ABC", "breadcrumb": ["根"]} for i in range(n)]

    def test_roll_and_summary(self):
        r = rolling_compile(self._chunks(4), _fake)
        self.assertEqual(len(r), 4)
        self.assertTrue(r[1]["summary"].startswith(r[0]["summary"]))

    def test_merge(self):
        chunks = [
            {"text": "块1", "breadcrumb": ["根"]},
            {"text": "MERGE块2", "breadcrumb": ["根"]},
            {"text": "块3", "breadcrumb": ["根"]},
        ]
        r = rolling_compile(chunks, _fake)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[1]["merged_blocks"], 2)

    def test_rewritten_preserved(self):
        r = rolling_compile([{"text": "块1内容", "breadcrumb": ["根"]}], _fake)
        self.assertIn("REW:", r[0]["rewritten"])

    def test_initial_summary(self):
        r = rolling_compile([{"text": "内容A", "breadcrumb": ["根"]}], _fake, initial_summary="START")
        self.assertTrue(r[0]["summary"].startswith("START"))

    def test_empty(self):
        self.assertEqual(rolling_compile([], _fake), [])


if __name__ == "__main__":
    unittest.main()
