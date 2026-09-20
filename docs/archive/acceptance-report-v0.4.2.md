# 验收报告 · md-rewrite-engine v0.4.2（内部一致性修复）

> 验收日期：2026-08-20｜范围：T-01~04 根治 v0.4.0 改定位时留下的 3 疏漏 + 1 未启用分支标注｜结论：✅ 通过

## 一、验收范围

| Task | 修复 | 判定 |
|---|---|---|
| T-01 | 剔 `traceability: per_claim`（与留白冲突）+ 删 `llm.py` 溯源死代码 | ✅ |
| T-02 | `user_prefs` 密度改 `general: 2`（示范数）+ `gate_check` 读配置（`_feynman_min`，不再硬编码）| ✅ |
| T-03 | 定稿"源数据外置 = 输入原文全文（clean.md 含画面切片）"写进手册 + v4 补落盘 | ✅ |
| T-04 | `executors.yaml` 标注 anthropic 为"未启用/预留"，脚本路径未验证 | ✅ |
| S2 | 补 gate_check 配置驱动用例（读配置/缺失回退），S2 137 全绿 high=0 | ✅ |

## 二、回归与终点一致性

- 全量回归 **166/166** + S2 **137/137** 全绿
- 一致性：`user_prefs.yaml feynman_density.general` ↔ `gate_check._feynman_min()` 实测一致（=2）；v4 复检 gate_check 仍 **PASS**（机械 100% + 6件套全 + 费曼每点≥2）

## 三、残留处置

- spec traceability 改为 optional（注释"v0.4.0 起停用"），不删字段保历史
- anthropic 通道【预留未启用】——真用脚本全自动前需验证，注释明示
- GLM 评分波动（85↔92）沿用"以 gate_check 硬门禁为准、评分波动由本体复核容忍"

## 四、证据单
- `temp/fixloop_evidence/round_102.md` 齐全（含现象/根因/修复/影响面 + 4 轮审核）

## 五、结论
v0.4.2 内部彻底修正完成：**定位与配置、代码不再打架**，人机接力 + 门禁机器 + 粒度一致。可交付。

> 验收报告位置：`docs/acceptance-report-v0.4.2.md`（v0.4.1 已归档 archive/）。CHANGELOG 追加 0.4.2。