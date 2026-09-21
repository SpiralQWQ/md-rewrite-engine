# 《目录契约》· md-rewrite-engine

> **状态**：✅ 已冻结（2026-08-19）｜ **版本**：v2.2
> **审批人**：用户（Tech Lead）｜ **约束**：后续新增目录/职责必须改此契约并重新冻结，严禁擅自加目录
> **变更记录**：v1.0（2026-08-13 冻结）→ v2.0（2026-08-16）新增执行者选择器（configs/executors.yaml + providers/executors.py）、S2 穷举脚本、docs 文档规范化（英文 kebab-case + archive 归档）→ v2.1（2026-08-18）新增 `core/toc.py`（篇内目录）→ v2.2（2026-08-19，对应 v0.4.1）新增 `scripts/gate_check.py`（门禁一键检查）与 `tests/scripts/`，docs 归档 v0.3.0/v0.4.0 验收报告。

## 1. 项目定位

`md-rewrite-engine` 是独立的笔记加工模块：把「清洗后的 md」重排成「AI 一眼能读懂的 md」（OKF 对齐）。
**唯一职责**：md → AI 友好 md 的转换。**不碰**媒体转写、**不碰**文档解析、**不碰**文本清洗（上游工具可任选，如 text-cleaning-engine）。

**v0.3.0 形态**：**人机接力**——rewrite/reconcile 由本体（Claude 对话）亲自做，脚本降级为「能力函数库」（机器兜底 + GLM 质检/评分），质量靠 fail-closed 门禁。

## 2. 接口边界（谁生产 md，谁负责组装）

```
[视频线] 转写json + visual.txt ──组装(归transcription-tools)──→ 半成品md ──清洗──→┐
[文档线] MinerU ──清洗──→ 清洗后md ───────────────────────────────────────→┤
                                                                          ▼
                                                    md-rewrite-engine（本模块）→ AI 友好 md
```
- **输入**：只收「清洗后的 md」（形态 A）。不支持收转写 json/txt —— 组装是生产方（视频线）的职责。
- **输出**：按 `configs/note_style_spec.yaml` 的 AI 友好 md（含 OKF 字段）。
- **兼容**：老流程（`transcription-tools` 直接交给 Claude 生成）不改、照用；本模块是新增独立路。

## 3. 范式选择：混合模式（分层 + 职责域）

不是范式 A（页面<10 小项目）、不是纯范式 B（多业务域）。本模块是**单一职责的数据处理管线**，按"处理层"分域：
**cli（入口）→ services（编排+LLM）→ core（纯算法）+ providers（外部依赖适配）+ configs（配置）**

## 4. 目录树（嵌套 ≤3 层）

```
md-rewrite-engine/
├── README.md / CHANGELOG.md / requirements.txt / .env.example / .gitignore
├── configs/            # 配置域：规范/偏好/模型/执行者（与代码分离，代码不硬编码）
│   ├── note_style_spec.yaml   # AI 友好笔记规范（v1.3：结构/信息密度/互链/关联字段/置信度）
│   ├── user_prefs.yaml        # 偏好：分块大小/费曼密度/视觉保留
│   ├── models.yaml            # 模型档位：重排/质检/评分用哪个模型（脚本侧默认）
│   └── executors.yaml         # 执行者选择器（v0.3.0）：4 环节各自执行者（本体/glm/deepseek/anthropic）
├── core/               # 核心域：纯业务逻辑，零外部依赖（不 import 其他域）
│   ├── assemble.py     #   md → 内部结构（标题树/面包屑）
│   ├── chunk.py        #   机械粗切（段落边界 + 超长兜底）
│   ├── rewrite.py      #   AI 滚动编译纯算法
│   ├── verify.py       #   语义对账 + 评分 + 门禁 gate（纯算法）
│   ├── concepts.py     #   概念页（粗体术语抽取/聚合）
│   ├── md_index.py     #   总索引 index.md
│   ├── search.py       #   词法检索
│   ├── toc.py          #   篇内目录（标题→TOC，write_output 后处理自动生成）
│   └── __init__.py     #   ★ 公共 API 出口（index 角色）
├── services/           # 服务域：编排 + LLM 调用（单向依赖 core/providers/configs）
│   ├── orchestrator.py #   主流程 + 能力函数库（assemble_chunks/concept_map/write_output…）
│   ├── llm.py          #   LLM prompt 组装（P1-P5：重排/质检/评分/对账）
│   └── __init__.py
├── providers/          # 适配域：外部依赖具体实现
│   ├── llm_client.py   #   GLM/DeepSeek/Anthropic 封装（provider/model 解析 + 超时重试）
│   ├── executors.py    #   执行者选择器（v0.3.0）：配置生成/校验/渲染
│   ├── file_io.py      #   读写 md / 扫描目录（原子写 + 写锁）
│   ├── git_io.py       #   git 自动提交 / 分支 / diff（B1/C2）
│   └── __init__.py
├── src/md_rewrite_engine/
│   ├── __main__.py     # 入口：薄层，只解析参数 → 调 orchestrator（python -m md_rewrite_engine）
├── scripts/            # 构建/批量跑/门禁工具（gate_check.py：本体主控门禁一键检查）
│   ├── gate_check.py   #   门禁：机械对账/6件套/费曼/评分判定（打回闭环，退出码 0/1）
│   └── __init__.py
├── tests/              # 测试（镜像 core/services/scripts：tests/core/、tests/services/、tests/providers/、tests/scripts/）
│   ├── core/
│   ├── services/
│   ├── providers/
│   └── scripts/
├── docs/               # 文档（英文 kebab-case 命名；历史版本归档到 archive/）
│   ├── directory-contract.md        # ★ 本契约冻结件
│   ├── user-guide.md                # 使用手册
│   ├── orchestration-manual.md      # 本体主控编排手册
│   ├── capability-functions.md      # 能力函数清单
│   ├── prompt-family-p1-p5.md       # 提示词家族 P1-P5
│   ├── executor-selector-plan.md    # 执行者选择器需求与行动计划
│   ├── task-list-v0.3.0.md          # v0.3.0 施工 Task 清单
│   ├── acceptance-report-v0.3.0.md  # v0.3.0 验收报告
│   ├── parser-benchmark-report.md   # 解析底座选型实测
│   ├── engine-evaluation-report.md  # 重引擎评估
│   └── archive/                     # 历史版本存档（v0.1.0/v0.2.0）
└── temp/                # 临时文件（测试样本/穷举脚本/修复证据单）
    ├── s2_exhaustive/   # S2 穷举测试脚本（115 用例，全 mock）
    ├── fixloop_evidence/ # fixloop 修复证据单（round_N.md，git 忽略不入库）
    └── *.md             # 测试输入/输出样本（保留入库）
```

## 5. 单向依赖铁律（防架构腐化）

```
python -m md_rewrite_engine ──→ services ──→ core（纯算法）
              │  ├─→ providers（LLM/文件/git/执行者）
              └──→ configs（读配置）
```
- **core 零外部依赖**：不 import providers/services/configs，纯函数 + 数据结构 → 可单独单测、可复用
- **services 是唯一调 LLM/IO 的地方**：编排主流程
- **providers 只做读写适配**：不藏业务逻辑

## 6. 硬规则（禁止项）

| 禁止 | 说明 |
|---|---|
| ❌ 后缀目录 | 无 `.py`/`.md`/`txt` 目录 |
| ❌ 业务逻辑散落 utils | 纯函数放 core 职责模块，不建 utils 兜底 |
| ❌ 跨域 import 内部文件 | 必须走 `__init__.py` 公共出口 |
| ❌ 嵌套超 3 层 | 最多 `域/模块.py` |
| ❌ 测试/配置混入业务代码 | configs/、tests/、scripts/ 独立 |
| ❌ 真实 `.env` 入库 | 只入 `.env.example` |
| ❌ 硬编码模型名/路径 | 一律走 configs/ 或环境变量 |
| ❌ 临时产物入库 | `.env`、`__pycache__/`、`temp/fixloop_evidence/` 进 `.gitignore` |

## 7. 文档命名规范

- **文件名**：英文 kebab-case（如 `user-guide.md`、`acceptance-report-v0.3.0.md`），内容可为中文
- **历史版本**：归档到 `docs/archive/`，文件名带版本号（如 `task-list-v0.2.0.md`），头部标「已归档」
- **版本对齐**：验收报告 `acceptance-report-v0.X.Y.md`、施工清单 `task-list-v0.X.Y.md` 与 `CHANGELOG.md` 版本段一一对应

## 8. 新增变更流程

- 新增职责 = 改契约 + 重新冻结；不改变既有结构
- 用依赖方向审查（人工/脚本）防止架构腐化
