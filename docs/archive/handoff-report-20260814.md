> ⚠️ **已归档**：本文档为历史版本快照（2026-08-14），内容不更新；最新状态见 `../README.md` 文档表 + `CHANGELOG.md`。
# 交接报告 · 环节1「AI 友好笔记流水线」· 2026-08-14

> 给接手者：不看历史对话，只靠本文件 + 引用文档，就能接住项目、继续施工。

---

## 一、这是什么（一句话）

`md-rewrite-engine` 是 学习资料库的**环节1 模块**：把「清洗后的 md」转成「AI 一眼能读懂的 md」（AI 友好笔记）。即视频线 / 文档线两条链路的共同下游加工厂。

```
[视频线] 转写→组装(assemble_md.py)→清洗 ─┐
                                          ├→ 清洗后 md → [md-rewrite-engine] → AI 友好 md
[文档线] MinerU→清洗──────────────────────┘
```

## 二、当前进度总览

| 状态 | 内容 |
|---|---|
| ✅ 已完成 | 模块全框架（core/services/providers/cli）、41 单元测试 + 165 穷举测试、text-cleaning-engine 标题误删修复、note_style_spec v1.2、**A1 信息密度标准（本体重排 27KB 达标）**、报告改名 |
| 🔧 进行中 | 无（刚完成 A1，待 A2） |
| ⬜ 待做 | 修正计划：A2 chunk 段落切、A3 assemble 定位、B1-B4 增强、C1-C3 选型（见文档五） |

## 三、文件地图（避免混淆，先读这几个）

| 路径 | 干什么 | 优先级 |
|---|---|---|
| `_调研/github笔记格式调研/对比与建议/09_环节1_AI友好笔记流水线方案_v7.md` | **总纲蓝图**（调研 769 仓 + 117 仓 + 方案 + 重构决策） | 先读 |
| `md-rewrite-engine/docs/DIRECTORY_CONTRACT.md` | 目录契约（架构铁律：core 零依赖/单向依赖） | 改代码前必读 |
| `md-rewrite-engine/docs/修正计划_20260814.md` | **当前待办**（A/B/C 详细施工计划，含验收标准） | 施工依据 |
| `md-rewrite-engine/docs/TASK_LIST.md` | 15 个 Task（已全部完成） | 已完成清单 |
| `md-rewrite-engine/docs/验收报告_v0.1.0.md` | 验收结果 + fixloop 9 轮 | 结果证明 |
| `md-rewrite-engine/temp/fixloop_evidence/` | 20 份修复证据单（现象/根因/修复/影响面） | 排查历史 |
| `md-rewrite-engine/temp/taoci_input.md` | 测试输入（抖音简历图集 OCR+GLM 合并） | 实测样本 |
| `md-rewrite-engine/temp/taoci_output.md` | **A1 达标产出**（27KB，AI 友好笔记范本） | 质量标准参照 |

## 四、关键决策与依据（为什么这么做）

| 决策 | 依据 |
|---|---|
| 滚动编译（AI 一页页读+前文摘要） | 模型窗口物理上限；Karpathy LLM Wiki 模式（llm-wiki-compiler/750 等 14 仓） |
| 分层架构 core/services/providers/configs | 大厂后端范式；core 零依赖可单测 |
| 双模型质检 + 机械对账 + 评分门槛 | 你要"准确稳定"，靠代码强制不靠 AI 自觉（epub-extract/767、ParseBench/314） |
| **AI 友好 4 要素** | OKFy/761 + synthadoc/001 + textbook-to-note/728 + VaultForge/668 |
| 本体重排（rewrite 由 Claude 会话做）+ GLM 质检 + Qwen 评分 | 三方分工，你指定：我管最重要的 rewrite，GLM/Qwen 兜质检评分 |

## 五、下一步（修正计划 A/B/C，含验收标准）

- **A2 chunk 段落切**：无标题 md 按空行切（不切半句），单段超长才硬切；有标题仍按标题切；41+165 回归过
- **A3 assemble 定位**：无标题返回 1 根块（不建假树）；有标题正常建树
- **B1-B4 增强**：git 自动提交 / 语义对账 / 断点续跑 / 低置信标记
- **C1-C3 选型**：R1 解析底座实测 / R4 git 分支 / 其余增强

每项完成走 4 轮审核 + 证据单。

## 六、踩过的坑（接手者必读，别再踩）

1. **GLM 模型**：本账户 `glm-4.5-air` 有额度、`glm-4.6` **余额不足**（code 1113）。models.yaml 已锁 glm-4.5-air；DeepSeek 无 key，quality/scoring 走 GLM 需设 `MD_REWRITE_PROVIDER_QUALITY_CHECK=glm`（llm_client 支持环境变量覆盖 provider）。
2. **体量算错**：`len(str)//1024` 不可靠，用 `wc -c`。taoci_output 实际 27KB（脚本曾误报 11KB）。
3. **无标题 md 标题树白做**：视频线转写产物无 `#`，assemble 退化成 1 根块——修正方向是 A2 段落切 + A3 定位调整 + **AI 滚动补结构是主角**。
4. **增强清单 ≠ 可选**：报告列了 17 项增强，当时只做了框架，9 项没施工（语义分块/git/断点/低置信等）——这是本次"功能没实现"的根因，接手者按修正计划补齐。
5. **文档命名**：报告原叫 v3 内容到 v7（已改名）；文档多别乱加，新增先看有没有现成的。
6. **API key 安全**：GLM/Qwen key 在环境变量，输出时**别打印明文**（密钥遮蔽铁律）。

## 七、验收标准参照（A1 已达标范本）

`temp/taoci_output.md`（27KB）= 达标 AI 友好笔记范本：
- frontmatter 12 字段（8+OKF4）
- 8 个核心知识点 × 6 子项（定义/类比/原理/示例/为什么/易错点）
- 费曼题 8 组 × 10 道 = 80 道
- 附录完整原文（OCR+GLM 全量，不概括）
- sources 溯源到图 + confidence

后续 rewrite 产出低于此标准 = 不合格，打回。

---

*状态截至 2026-08-14。接手者从修正计划 A2 开始即可。*
