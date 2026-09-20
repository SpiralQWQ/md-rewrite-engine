> ⚠️ **已归档**：本文档为历史版本快照（v0.1.0），内容不更新；最新状态见 `../README.md` 文档表 + `CHANGELOG.md`。
# 补丁计划 · Task 清单（S1 穷举闭包）

> 依据：`09_环节1_AI友好笔记流水线方案_v7.md`（v7 最终版，3 项重构已确认）
> 状态：逐 Task 执行 + 4 轮审核（完成度/回归影响/隐蔽缺陷/代码质量），全过才进下一个
> 审核证据单：`temp/fixloop_evidence/round_N.md`（现象/根因/核心修复/影响面）

## 阶段 A · 清洗加固（已有成果收编）

| Task | 内容 | 验收点 |
|---|---|---|
| Task-01 | text-cleaning-engine 标题误删修复验证（白名单+序号识别，已改） | 复跑测试文本 5 标题恢复 + 答主名照删 + 真实 md 32 标题保留 + 仓库测试 8/8 |

## 阶段 B · md-rewrite-engine 施工（core → providers → services → cli → tests）

| Task | 内容 | 验收点 |
|---|---|---|
| Task-02 | `core/assemble.py`：md → 内部结构（标题树/面包屑） | 真实 md 解析出标题树，无 # 标记也能模式识别 |
| Task-03 | `core/chunk.py`：机械粗切（防超限 + 块间重叠） | 每块 ≤ max_tokens，带父标题面包屑，块间重叠 200 字 |
| Task-04 | `core/rewrite.py`：AI 滚动编译纯算法（滚动窗口/前文摘要/边界合并） | 长文本滚动处理不超限，摘要贯穿，可合并边界 |
| Task-05 | `core/verify.py`：语义对账 + 质量评分（纯算法） | 丢失知识点检出，评分阈值打回逻辑正确 |
| Task-06 | `providers/file_io.py`：读写 md / 扫描目录 | 读/写/扫描路径正确，中文编码 UTF-8 |
| Task-07 | `providers/llm_client.py`：GLM/DeepSeek 封装（按 models.yaml） | 模型名从配置读，无硬编码，超时/重试 |
| Task-08 | `services/llm.py`：prompt 组装（重排/质检/评分） | 三种 prompt 结构完整，注入术语表+前文摘要 |
| Task-09 | `services/orchestrator.py`：主流程编排（读→切→重排→验→写） | 一条完整链路跑通，不合格打回 |
| Task-10 | `cli.py`：入口（薄层） | 参数解析正确，调 orchestrator，防呆 |

## 阶段 C · 规范 + 视频线接口

| Task | 内容 | 验收点 |
|---|---|---|
| Task-11 | note_style_spec v1.2 OKF 字段落位（confidence/sources/status/wikilinks） | configs yaml 校验通过，与 v1.1 兼容 |
| Task-12 | `transcription-tools` 加"组装 md"步骤（json+txt → 半成品 md） | 输入转写 json + visual txt → 输出半成品 md，老提示保留 |

## 阶段 D · 测试 + 验收

| Task | 内容 | 验收点 |
|---|---|---|
| Task-13 | tests 全量（core/services 镜像结构） | 覆盖各模块，核心路径 + 边界全测 |
| Task-14 | 最终验收：全量 Task 穷举式回归 + 终点一致性 | 全部 Task 达标，终点一致 |
| Task-15 | CHANGELOG（开源规范） | 命名/位置符合规范 |

## 依赖顺序

```
A(Task-01) → B(Task-02→10) → C(Task-11,12) → D(Task-13,14,15)
B 内部：core 先行（零依赖可单测）→ providers → services → cli
```
