# md-rewrite-engine

<p align="center">
  <a href="README.md"><kbd>🇺🇸 English</kbd></a> · <kbd>🇨🇳 简体中文</kbd>
</p>

<p align="center">
  <a href="https://github.com/SpiralQWQ/md-rewrite-engine/releases"><img src="https://img.shields.io/github/v/tag/SpiralQWQ/md-rewrite-engine?label=version" alt="version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL%203.0%20%7C%20Commercial-blue" alt="license"></a>
  <a href="https://github.com/SpiralQWQ/md-rewrite-engine/stargazers"><img src="https://img.shields.io/github/stars/SpiralQWQ/md-rewrite-engine?style=social" alt="stars"></a>
</p>

**清洗后的 md → AI 一眼能读懂的 md（人机接力 + 质量门禁）**

`md-rewrite-engine` 是一条独立的笔记加工流水线：把「清洗后的普通 md」（视频转写 / 文档 OCR / PDF 解析产物）重排成「AI 能直接照着教学的 md」——含滚动编译（防上下文超限）、确定性验证层（机械对账 / 语义对账 / GLM 质检 / 评分门槛）、OKF 教学结构对齐。

## 为什么做这个

让 LLM 直接重写学习笔记会漂移：漏概念、造词、而且"自评很好"没有证据。本项目把质量做成**可测量、可强制**：

- 每次重写必须过**机械门禁**（数字硬判定 ≥90% / 6 件套齐全 / 费曼示范 / GLM 评分达标）——任一不达标即打回，绝不"信任通过"；
- 每次打回都带**问题清单**，针对性修补（反馈累积；每块 ≤4 次，超限挂起待人工）；
- 教学结构**写死在配置**（6 件套 + 费曼 4 角度），输出形状不随模型心情变。

## 特性

- **人机接力**：rewrite / reconcile 由本体（Claude 对话）亲自做，脚本降级为「可单环节调用的能力函数库」——机器干能干的，质量靠门禁兜底。
- **执行者可配**：4 环节（rewrite / reconcile / quality_check / scoring）独立配执行者，支持 `claude(本体) / glm / deepseek / anthropic` 混合。
- **fail-closed 门禁**：机械对账（数字硬判定 ≥90%）/ 6 件套完整 / 费曼示范 / GLM 质检评分任一不达标 → 不能「通过」。
- **机器门禁一键检查**：`scripts/gate_check.py`——本体重排完必跑，一次拿到机械对账/6件套/费曼/评分硬指标，不达标强制打回（≤4 次 → 挂起），**质量靠门禁不靠自觉**。
- **防死循环**：每块独立 4 次修补额度，超限挂起待人工；打回 = 带问题清单针对性修补（反馈累积）。
- **教学结构写死**：6 件套（定义/类比/原理/示例/为什么重要/易错点）+ 费曼 4 角度 + 附录外置（原文存源文件，不干扰教学上下文）。
- **长上下文防隔离**：概念地图先行 + 逐块带「全局地图/前文摘要/后文预告/块间重叠」。

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配密钥（复制 .env.example 为 .env 并填入）
GLM_API_KEY=你的智谱key

# 3. 重排一份清洗后 md
python cli.py 输入.md --output 输出.md

# 4. 课程级工具
python cli.py --index 课程目录           # 生成 index.md 总索引
python cli.py --validate-links 课程目录  # 校验 [[链接]] 悬空
python cli.py --concepts 课程目录        # 生成概念页
python cli.py --search 关键词 --input 课程目录  # 词法检索
```

> **推荐用法（本体主控）**：把转写丢给 Claude 对话，按 `docs/orchestration-manual.md` 10 步亲自编排，脚本只调机器活（质检/评分/对账/输出）。见 `docs/user-guide.md`。

## 执行者配置

默认（`configs/executors.yaml`）：

| 环节 | 执行者 | 说明 |
|---|---|---|
| rewrite 重排 | 本体（claude） | 亲自做（要上下文、要详细） |
| reconcile 对账 | 本体（claude） | 亲自做（要理解内容才能查概念） |
| quality_check 质检 | glm | GLM 先挑，人工复核 |
| scoring 评分 | glm | GLM 打分，人工确认 |

换执行者：改 `configs/executors.yaml` 或设环境变量 `MD_REWRITE_PROVIDER_<KEY>` / `MD_REWRITE_MODEL_<KEY>` 覆盖。

## 架构

```
cli.py ──→ services ──→ core（纯算法）
              │  ├─→ providers（LLM/文件/git/执行者）
              └──→ configs（规范/偏好/模型/执行者）
```

- **core/**：纯算法零外部依赖（assemble / chunk / rewrite / verify / concepts / md_index / search）
- **services/**：编排 + LLM prompt（orchestrator / llm）
- **providers/**：外部适配（llm_client / file_io / git_io / executors）
- **configs/**：note_style_spec（教学结构）/ executors（执行者）/ models（模型档位）/ user_prefs（偏好）

核心契约见 `docs/directory-contract.md`。

## 测试

```bash
python -m pytest tests/ -q          # 单元测试 169
python tests/exhaustive/s2_exhaustive.py   # S2 穷举 137（全 mock）
python scripts/gate_check.py 笔记.md --src 原文.md   # 门禁一键检查（PASS/FAIL+问题清单）
```

## 文档

| 文档 | 内容 |
|---|---|
| `docs/user-guide.md` | 怎么跑 / 配执行者 / 换执行者 / 换会话复用 |
| `docs/orchestration-manual.md` | 本体主控 10 步编排流程 |
| `docs/capability-functions.md` | 能力函数清单（脚本 = 工具库） |
| `docs/prompt-family-p1-p5.md` | P1-P5 提示词家族（详细度/结构/检查写死） |
| `docs/directory-contract.md` | 分层契约 |
| `docs/archive/` | 历史版本存档（施工清单/验收/评估报告） |

## 路线图

见 `ROADMAP.md`（近期：diff-only 门禁审查、执行者自动降级、英文笔记模板）。

## FAQ（常见问题）

**问：重排环节必须在对话里用 Claude 吗？**
不必——脚本可以端到端驱动任何已配置的执行者（`cli.py 输入.md`）。推荐"人机接力"是因为重排质量取决于"整篇都在上下文里"，这正是对话模型擅长的。无论哪种方式，门禁（`gate_check.py`）都兜底。

**问：gate_check 对 ASR 转写总是 FAIL（数字对不上）？**
那是机械对账在干活——但请先确认 `--src` 传入的是**清洗后**的原文；数字阈值在 `configs/user_prefs.yaml`。

**问：能换别的 LLM 供应商吗？**
可以：`glm` / `deepseek` / `anthropic` 已接好；任何 OpenAI 兼容 endpoint 都能在 `providers/llm_client.py` 的 `_ENDPOINTS` 里加。Key 只从环境变量读。

**问：英文素材能用吗？**
教学模板目前按中文调优（六件套/费曼角度）。流水线本身与语言无关；英文 spec 变体在[路线图](ROADMAP.md)上。

## 许可证

开源版本使用 [AGPL-3.0](LICENSE)。商用授权见 [COMMERCIAL.md](COMMERCIAL.md)。

## 打赏

如果这个项目对你有帮助，欢迎请作者喝杯咖啡 ☕。打赏完全自愿——项目永久免费开源。

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="微信赞赏" width="200">
  <img src="assets/donate_alipay.jpg" alt="支付宝" width="200">
</p>
