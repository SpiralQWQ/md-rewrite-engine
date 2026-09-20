> ⚠️ **已归档**：本文档为历史版本快照（v0.3.0），内容不更新；最新状态见 `../README.md` + `CHANGELOG.md`。
# 验收报告 · md-rewrite-engine v0.3.0（执行者选择器 + 本体主控全量验收）

> 验收日期：2026-08-16｜依据：`docs/task-list-v0.3.0.md` + `docs/executor-selector-plan.md` + `~/.claude/spec/_exhaustive_test_charter.md`｜结论：✅ 通过

## 一、验收范围（6 阶段 27 Task）

| 阶段 | Task | 内容 | 状态 |
|---|---|---|---|
| 1 执行者选择器 | 01-03 | executors.yaml（4 环节可配执行者）+ 对话询问 + 路由按配置走 | ✅ |
| 2 本体参与骨架 | 04-07 | 能力函数库（assemble_chunks/write_output 等）+ 主控编排手册 + 闭环验证 | ✅ |
| 3 本体主导全局 | 08-12 | 概念地图先行 + 语义分块 + 逐块带上下文 + 整体审 | ✅ |
| 4 提示词家族 | 13-18 | P1 重排 / P2 自查 / P3 对账 / P4 GLM 质检 / P5 GLM 评分（6件套+费曼4角度写死） | ✅ |
| 5 验证打回闭环 | 19-23 | fail-closed 门禁（gate）+ 每块独立 4 次修补 + 原文保护/机械对账 ≥90% + 反馈累积 | ✅ |
| 6 收尾 | 24-27 | 附录外置 + 输出笔记 + 使用手册 + 最终回归 | ✅ |
| S2 穷举 | 1 轮 115 用例 | 路径/边界/终点一致性，收敛 high=0 | ✅ |
| S4 验收 | — | 全量回归 + 终点一致性分组比对 + 证据单核查 + 本报告 | ✅ |

## 二、全量回归与终点一致性

- **单元测试 134/134 通过**（S1 阶段 6 末基线 134 全绿，S2 修复后复跑仍全绿）
- **S2 穷举脚本 115/115 通过**（`temp/s2_exhaustive/s2_exhaustive.py`，全 mock 不耗 LLM 额度）
- **终点一致性分组比对**：

| 组 | 殊途同归 | 结果 |
|---|---|---|
| 组1 | process 失败模式（文件不存在/空内容/LLM异常/非str路径）→ 统一 error dict | ✅ |
| 组2 | call_llm 失败模式（缺key/缺base_url/4xx/5xx耗尽/超时/结构异常）→ 统一 RuntimeError | ✅ |
| 组3 | 课程函数（build_course_index/validate_course_links/build_concepts/search_course/process_course）缺目录/无笔记 → 统一 error dict | ✅ |
| 组4 | resolve_model 优先级链（env > executors > models.yaml > 默认），未知 key 回落 glm-4.5-air | ✅ |
| 组5 | _provider_of 优先级链（env > executors.provider > executors.executor > 内置） | ✅ |
| 组6 | 断点续跑：输入未变命中缓存 / 变化失效 / 损坏回落 {} | ✅ |
| 组7 | write_output 笔记/源分离终点（正常/缺源/空参/异常 → 统一 dict） | ✅ |

## 三、S2 穷举修复的缺陷（穷举价值）

| 缺陷 | 严重度 | 根因 | 修复 |
|---|---|---|---|
| `resolve_model` 未知 key 返回空串 | MED | `_DEFAULT_MODELS.get(key, "")` 兜底取空 | 回落 `_DEFAULT_MODELS["rewrite"]`（providers/llm_client.py） |
| `process` 负 retries 静默跳过全部验证 | MED | `range(max_rewrite_retries+1)` 空循环，fail-closed 被绕过 | `max(0, ...)` clamp（services/orchestrator.py） |

**收敛判定**：high=0 && medium=0（已修）&& low=0 → **fixloop 收敛** ✅

## 四、证据单核查

- `temp/fixloop_evidence/round_76~93` **共 90 份齐全**（round_90/91 由 round_92 合并覆盖阶段 6 收尾）
- 均含「问题现象 / 根因 / 核心修复 / 影响面」四项 + 4 轮审核，非罗列完成项 ✅

## 五、架构与质量结论

- **core 零依赖铁律保持**：assemble/chunk/rewrite/verify/concepts 等纯函数零 IO
- **人机接力落地**：本体主控编排手册（10 步）+ 能力函数库（7 函数），脚本=工具库、本体=决策者
- **执行者可配**：executors.yaml 4 环节独立配置，支持 claude(本体)/glm/deepseek/anthropic 混合
- **质量靠门禁**：fail-closed gate（机械对账/质检/评分任一不达标不能"通过"）+ 每块独立 4 次修补 + 超限挂起
- **无硬编码**：模型名/路径走 configs/环境变量；密钥走 .env（仅提交 .env.example）
- **防回归**：S2 穷举脚本固化在 temp/s2_exhaustive/，可重复跑

## 六、结论

执行者选择器 + 本体主控全部 27 Task + S2 穷举 115 用例 + S4 终点一致性 7 组全部通过。
v0.2.0 的纯脚本流水线已升级为"**本体主导 + 机器兜底**"的人机接力模式，质量靠 fail-closed 门禁不靠自觉，可发布 **v0.3.0**。

> 遗留（非阻断，记录在案）：① anthropic 通道需配好环境变量后才启用（直连/代理均可）；② 本体主控的 rewrite/reconcile 环节依赖对话内执行（脚本不代跑），换会话需按 `docs/user-guide.md` 复用。
