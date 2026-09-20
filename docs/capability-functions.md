# 能力函数清单 · 本体主控编排（B 方向，v0.3.0）

> 日期：2026-08-16｜定位：执行者选择器阶段 2——**我（本体）主控**，脚本降级为"我可逐环节调用的函数库"。
> 目标：我读转写 → 我重排 → 我调脚本跑机器活（质检/评分/对账/输出）→ 全程上下文连贯。

---

## 一、分工：我直接做 vs 调脚本

| 环节 | 谁做 | 说明 |
|---|---|---|
| 读转写 / 抽概念地图 | **我** | 我读全文，心里有全局 |
| 逐块重排 / 建结构 | **我** | 我的核心创作（带全局地图） |
| 自查 / 概念对账 | **我** | 我判断（灵活标准） |
| 复核 GLM 质检/评分 | **我** | 区分真问题/噪音 |
| 物理分块兜底 | 调脚本 | 仅超长时兜底切 |
| GLM 质检 / 评分 / 语义对账 | 调脚本 | 机器先挑，我复核 |
| 机械对账（关键点覆盖率） | 调脚本 | 硬性兜底防漏 |
| 输出笔记 + 转写外置 | 调脚本 | 落盘 |

## 二、能力函数清单（我可单环节调用）

| # | 函数 | 接口 | 返回 | 来源 |
|---|---|---|---|---|
| 1 | `assemble_chunks(text)` | 全文 → 物理分块（段落边界，超长兜底） | `list[Block]` | 封装 assemble+chunk_blocks |
| 2 | `mech_reconcile(orig, rewritten)` | 原文 vs 重排 | `{missing, coverage, ok}` | V.reconcile（已有） |
| 3 | `glm_quality(text)` | 重排结果 → GLM 挑错 | `list[str]` | llm.run_quality（已有） |
| 4 | `glm_score(text)` | 重排结果 → 评分 | `(score, reason)` | llm.run_scoring（已有） |
| 5 | `glm_reconcile(orig, rewritten)` | 语义对账（辅助我对账） | `list[str]` | llm.run_reconcile（已有） |
| 6 | `extract_terms(text)` | 粗体术语（概念地图参考） | `list[str]` | CN.extract_terms（已有） |
| 7 | `write_output(note, source, out_dir)` | 笔记落盘 + 转写外置源文件 | `path` | **新封装** |

## 三、数据结构（约定）

- **块 Block**：`{title, text, breadcrumb}`（现有）
- **概念地图**：`list[{"name", "block_ids"}]`（我抽，辅助不遗漏）
- **问题清单**：`list[str]`（GLM 质检 + 我复核后）
- **输出**：笔记.md + 源数据/转写.md

## 四、我主控的编排顺序（B 流程）

```
1. 我读全文（脚本 read_md 给我）
2. 我抽概念地图（可参考 extract_terms）
3. 我调 assemble_chunks 拿物理块（仅超长兜底）
4. 我逐块重排（带全局地图 + 前文摘要 + 后文预告 + 块间重叠）
5. 我自查（P2 提示词）
6. 我概念对账（P3 + mech_reconcile 兜底）
7. 我调 glm_quality + glm_score → 复核（P4/P5）
8. 有真问题 → 我针对性修补 → 再验（每块独立 ≤4 次 → 挂起）
9. 我通读整篇整体审
10. 我调 write_output 输出（笔记 + 转写外置）
```

---

*Task-05 按此清单实现缺的封装（assemble_chunks / write_output）；其余复用现有函数。*
