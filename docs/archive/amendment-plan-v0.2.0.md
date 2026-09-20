> ⚠️ **已归档**：本文档为历史版本快照（v0.2.0），内容不更新；最新状态见 `../README.md` 文档表 + `CHANGELOG.md`。
# 环节1 修正施工计划 v3（详细版：做什么 / 做到什么程度）

> 依据：补丁计划实现核对 + 用户质疑（无标题 md 切分 / AI 友好信息密度 / 增强未落地）+ 调研报告回顾（AI 整门课看懂缺"复利三件套"）。
> 每个任务写明：**目标 / 具体改动 / 验收标准（做到什么程度算完成）/ 涉及文件**。
> 验收标准可测——不满足即不算完成。
>
> **v3 新增：D 类「内容结构补丁」**（总索引 / 互链 / 概念页等 8 项）——解决"单篇 AI 能读懂，整门课会迷路"。
> 依据：`_调研/github笔记格式调研/对比与建议/09_环节1_AI友好笔记流水线方案_v7.md` §二（本项目缺点）+ `09_环节1_补丁重构计划报告_769仓精读版.md` §十（二次开发方案）+ student-llm-wiki / textbook-to-note / OKFy 等仓库报告。
> 分工：调研报告 = 为什么（依据保留）；本计划 = 做什么（施工清单）。

---

## 📌 实施总览

| 优先级 | 任务 | 一句话 | 验收（做到什么程度） |
|---|---|---|---|
| **P0** | A1 rewrite 信息密度 | 让产出达"4 要素"标准 | taoci 实测产出含全部 4 要素 |
| **P0** | A2 chunk 段落切 | 无标题 md 按段落切 | 不切句子中间 |
| **P0** | A3 assemble 定位 | 有标题用之、无标题粗切 | 无标题不崩、不建假树 |
| P1 | B1 git 自动提交 | 每步改动留版本 | 可回滚任意一步 |
| P1 | B2 语义对账 | 概念级覆盖核对 | GLM 辅助检出语义缺失 |
| P1 | B3 断点续跑 | 中断可续 | 重跑跳过已完成单元 |
| P1 | B4 低置信标记 | 标出 AI 没把握处 | 输出含 [低置信] 标记 |
| P2 | C1 解析底座实测 | 定 R1 | 实测报告结论 |
| P2 | C2 R4 git 安全 | 分支+diff+回滚 | 重排前建分支可回滚 |
| P2 | C3 其余增强 | 增量/理由/引擎/schema | 逐项验收 |
| **P0** | D1 总索引 index.md | 建知识点地图 | AI 只读它即知课程结构/教学顺序 |
| **P0** | D2 [[链接]] 互链 | 前置/后继知识点互链 | 跨讲引用可点、无悬空链接 |
| P1 | D3 frontmatter 关联字段 | 加前置/后继/相关字段 | 依赖关系机器可读、与互链同步 |
| P1 | D4 条目级引用 | 示例标"第X讲 HH:MM" | 抽查 10 条出处与实际对应 |
| P1 | D5 [AI推断] 标注 | 区分视频原话 vs AI 补充 | 输出含 [AI推断] 标记 |
| P1 | D6 confidence 落值 | 实际填 high/med/low | frontmatter 非空、有人核验 |
| P1 | D7 概念页 | 一概念一页跨讲累积 | 核心概念有聚合页 + 出现讲次链接 |
| P2 | D8 极简词法检索 | 零依赖关键词搜索 | 输入关键词返回相关笔记+段落 |

---

## 🔴 P0 · 产出质量（当前根因，必须先做）

### A1 · rewrite 信息密度标准（当前"信息少"的直接根因）

**目标**：让 rewrite 产出达到「AI 友好 md 4 要素」标准，不再压缩丢信息。

**AI 友好 md 4 要素**（源自 OKFy/761 + synthadoc/001 + textbook-to-note/728 + VaultForge/668）：
1. **typed frontmatter**：`type/confidence/sources/status/tags` 等 12 字段
2. **结构化章节**：概述 → 核心知识点 → 词汇表 → 思考题 → 完整原文附录
3. **完整信息密度**：每知识点含【定义/通俗类比/原理/示例/为什么重要/易错点】；费曼题 ≥10 道/知识点；附录保留完整原文（不概括）
4. **溯源+置信度**：每条内容标来源（sources 具体到图/句）+ confidence

**具体改动**：
- A1a：更新 `configs/note_style_spec.yaml`——加"4 要素"字段定义（如 `info_density: [定义/类比/原理/示例/为什么/易错点]`、`feynman_per_kp: 10`、`appendix: full_original`、`traceability: per_claim`）
- A1b：更新 `services/llm.py` 的 `build_rewrite_prompt`——system 强制 4 要素（每知识点必须展开 6 子项、费曼题 10 道、附录全文、标来源），否则视为不合格
- A1c：用 `temp/taoci_input.md` 实测——本体重排产出新笔记，核对 4 要素

**验收标准**：
- [ ] 产出 frontmatter 含 12 字段（8 + confidence/sources/status/wikilinks）
- [ ] 每个核心知识点含全部 6 子项（定义/类比/原理/示例/为什么/易错点）
- [ ] 费曼题 ≥10 道/知识点
- [ ] 附录含**完整原文**（OCR + GLM 全量，不概括）
- [ ] 每条知识点标来源（对应图 1-5）+ confidence
- [ ] 与旧笔记（08_…27KB）体量相当（≥20KB）

**涉及文件**：`configs/note_style_spec.yaml`、`services/llm.py`、`temp/taoci_output.md`

---

### A2 · chunk 段落边界切（无标题 md 乱切问题）

**目标**：无标题 md 不再按字符硬切，改按"段落边界"（空行分隔）切——每块是完整段落，AI 读到的是连贯语义。

**具体改动**：
- `core/chunk.py`：`_split_lines_by_chars` 优先按空行切分（段落为单位），仅当**单段超长**时才字符硬切兜底
- 有标题 md 仍按标题边界切（不变）

**验收标准**：
- [ ] 无标题 md（流水账）：每块不包含"半句话"（段落边界切）
- [ ] 单段超长（>max_chars）：才字符硬切（兜底）
- [ ] 有标题 md：仍按标题切（回归不破坏）
- [ ] 既有 41+165 测试全过

**涉及文件**：`core/chunk.py`、`tests/core/test_chunk.py`

---

### A3 · assemble 定位调整（无标题 md 标题树白做问题）

**目标**：标题树从"必须建树"降级为"有标题则用之、无标题则粗切打底"——无标题 md 不建假树、不报错、直接粗切。

**具体改动**：
- `core/assemble.py`：无标题 md（仅 1 个根块时）→ 正常返回根块（不产生假标题），下游 chunk 按段落切
- 文档/报告层面：明确 assemble 是"粗切打底"，不是"标题识别主角"（主角是 AI 滚动）

**验收标准**：
- [ ] 无标题 md → assemble 返回 1 个根块（不崩、不建假树）
- [ ] 有标题 md → 正常建树（回归）
- [ ] 纯段落 md → 可被 A2 段落切处理

**涉及文件**：`core/assemble.py`、`tests/core/test_assemble.py`

---

## 🟡 P1 · 增强补齐（首发档 + 关键稳定性）

### B1 · git 自动提交（增强 12）

**目标**：每步 AI 改动留版本，可回滚任意一步。

**具体改动**：`services/orchestrator.py`——每次 write_md 前，若目标在 git 仓库则 `git add + commit`（带 message：Task 阶段 + 时间）

**验收标准**：3 步重排 → 3 次 git commit；`git log` 可回溯；`git checkout` 可回滚任一步

**涉及文件**：`services/orchestrator.py`、`providers/file_io.py`（可加 git 操作）

---

### B2 · 语义级对账（增强 8）

**目标**：verify 从"词级"升级到"语义级"——GLM 判断"概念是否覆盖"，不只数关键词。

**具体改动**：`core/verify.py` 加 `semantic_reconcile(original, rewritten, _call)`——调 GLM 输出"原文核心概念清单"vs"重排缺失概念"

**验收标准**：GLM 能检出"词级对账漏掉但概念级缺失"的 case（如"STAR法则"被改写为"四段式描述"）

**涉及文件**：`core/verify.py`、`services/llm.py`（加 semantic 环节）

---

### B3 · 断点续跑（增强 13）

**目标**：orchestrator 中断后重跑，跳过已完成单元。

**具体改动**：`services/orchestrator.py`——每单元完成后写状态（已处理 chunk 数/摘要链到 `temp/` 状态文件）；重跑时读状态跳过

**验收标准**：模拟中断（中途 kill）→ 重跑 → 跳过已完成单元，输出与一次跑完一致（终点一致）

**涉及文件**：`services/orchestrator.py`、新增状态文件逻辑

---

### B4 · 低置信标记（增强 10）

**目标**：AI 没把握处标 [低置信]，供人工抽查。

**具体改动**：`services/llm.py`——run_rewrite prompt 要求"不确定处输出时标 `[低置信]`"；orchestrator 收集低置信列表

**验收标准**：AI 对存疑内容标 [低置信]；orchestrator 返回 low_conf 列表；可与视频线 review_hint 对接

**涉及文件**：`services/llm.py`、`services/orchestrator.py`

---

## 🟢 P2 · 选型落地

### C1 · R1 解析底座实测

**目标**：定 arborparser vs markdown-it-py（含无标题 md）。

**具体改动**：装两库，拿真实"复杂 md（表格/公式）+ 无标题 md"跑对比，出实测报告

**验收标准**：实测报告：哪个对复杂结构解析准、哪个对无标题 md 支持好 → 定 R1

**涉及文件**：实测脚本 + 报告文档

---

### C2 · R4 git 分支安全（增强 12 强化）

**目标**：重排前建分支 + diff 预览 + 可回滚。

**具体改动**：orchestrator 重排前 `git checkout -b rewrite-<ts>`；产出后 diff 摘要

**验收标准**：重排前自动建分支；可 `git checkout master` 回滚

**涉及文件**：`services/orchestrator.py`

---

### C3 · 其余增强（14 增量 / 16 理由报告 / 17 重引擎 / 11 严格 schema）

**目标**：补齐剩余增强，逐项验收。

**具体改动**：
- C3a 增量处理（增强 14）：只处理变更的 md（按 mtime）
- C3b 删除带理由报告（增强 16）：AI 删除/修改输出理由
- C3c 引重引擎（增强 17）：评估引入 llm-wiki-compiler（npm）利弊，或维持自研
- C3d 严格 schema（增强 11）：jsonschema 校验 AI 输出结构

**验收标准**：逐项按上述定义验收

---

## 🟠 D · 内容结构补丁（AI 看懂整门课，v3 新增）

> **为什么补**：单篇笔记 AI 能读懂（A1 已达标），但一整门课（30 讲）AI 会迷路——不知道教学顺序、跨讲引用靠猜、核心概念散落各讲讲得前后矛盾。调研结论 = 缺"复利三件套"：**总索引 + 互链 + 置信度**。
> **依据**：`09_环节1_AI友好笔记流水线方案_v7.md` §二（本项目缺点）+ `09_环节1_补丁重构计划报告_769仓精读版.md` §十（md_index / md_backlink / md_meta 二次开发项）+ student-llm-wiki / textbook-to-note / OKFy 仓库报告。
> **定位**：全是纯 Markdown 轻补丁，不引数据库/向量库；D 排在 A 产出达标之后做（有内容才编地图）。

### D1 · 总索引 index.md（知识点地图）

**目标**：每门课建一张"知识点地图"（index.md），AI 先读它就知道：课有哪些讲次、先后顺序、每讲讲什么。解决"AI 不知道先教哪个后教哪个"。

**具体改动**：
- 新增索引生成逻辑（core 模块 `md_index.py` 或 orchestrator 服务）：扫描课程目录全部笔记 frontmatter + 标题 → 生成 `index.md`（讲次列表 + 一句话摘要 + 知识点链接 + 统计块）
- 索引格式参照 OKF 约定：`index.md` 根带课程元数据（`okf_version`），每讲 = `[[链接]]` + 一句话 + 元数据
- 生成时机：A1 产出后统一跑一次；后续随 D3 字段增量更新

**验收标准**：
- [ ] 每门课生成 `index.md`，含全部讲次 `[[链接]]` + 每讲一句话摘要
- [ ] AI 只读 index.md 即可说出"课程结构 + 教学顺序"
- [ ] 索引链接全部有效（无死链）

**涉及文件**：新增 `core/md_index.py`、`services/orchestrator.py`
**依据**：student-llm-wiki `index.md`（总目录 Master catalog）/ okf-skills index 约定 / 769仓精读版 §十 `md_index.py`（markdown-notes-tree/Waypoint）/ v7 §五 经验 5（索引替代全文倾倒省 token 66%）

### D2 · [[链接]] 互链（前置知识点 / 后继讲）

**目标**：讲次之间用 `[[链接]]` 互链——每讲开头"前置知识"引用定义它的讲次，结尾"后继讲"指向后续。AI 跨讲追引不靠猜，概念一致。

**具体改动**：
- `configs/note_style_spec.yaml` 加互链规范：前置知识 / 后继讲 / 相关知识点 用 `[[讲次#知识点]]` 形式
- `services/llm.py` 重排 prompt 要求：提到前置概念时自动加链接，重复概念用链接引用而非重写（textbook-to-note 引用纪律）
- 生成后校验：链接目标存在；缺目标标 warning 不报错（OKFy 解析约定）

**验收标准**：
- [ ] 每篇笔记含 ≥1 个 `[[前置]]` + ≥1 个 `[[后继]]`（末篇除外）
- [ ] 链接目标存在，无悬空链接（或显式标 warning）
- [ ] 重复概念用链接引用而非重写

**涉及文件**：`configs/note_style_spec.yaml`、`services/llm.py`、`core/verify.py`（链接校验）
**依据**：student-llm-wiki `[[链接]]` / textbook-to-note `[[#章节]]` 引用规则 / OKFy wikilink 解析约定 / 项目基准 §六（图谱互联）

### D3 · frontmatter 关联字段（前置 / 后继 / 相关）

**目标**：让"依赖关系"机器可读——frontmatter 加 `prerequisites`（前置知识点）、`next`（后继讲）、`related`（相关）。AI 可编程地判断教学顺序，不只靠 AI 自觉读正文。

**具体改动**：
- `configs/note_style_spec.yaml` frontmatter 增 `prerequisites/next/related`（v1.2 → v1.3）
- AI 生成时按实际内容填；`core/verify.py` 机器校验字段非空且指向存在
- 与 D2 互链保持同步（字段值 = [[链接]] 目标）

**验收标准**：
- [ ] frontmatter 含 prerequisites/next/related（末篇 next 可为空）
- [ ] 值指向真实讲次/知识点，可机器校验
- [ ] 字段与 D2 [[链接]] 一致（不同步 = 不过）

**涉及文件**：`configs/note_style_spec.yaml`、`services/llm.py`、`core/verify.py`
**依据**：项目基准 §2.2 缺点（缺前置/后继/相关字段）/ Ranedeer 前置递进链 / 769仓精读版 §八 `md_meta.py`（frontmatter 补全 + Schema 校验）

### D4 · 条目级引用（示例标"第X讲 HH:MM"）

**目标**：知识点"示例/原句"栏不再笼统"来自转写"，而标具体出处 `(来源: 第X讲 HH:MM)`。AI 溯源精确到句/时间，防幻觉。

**具体改动**：
- 视频线转写 json 带时间戳 → 组装 md 时保留；AI 重排"示例/原句"栏标注 `(来源: 第X讲 HH:MM)`
- 无时间戳（文档线）标注 `(来源: 第X页 / 章节)`

**验收标准**：
- [ ] 每个"示例/原句"有可追溯出处（时间戳或页/章节）
- [ ] 抽查 10 条：出处与实际内容对应

**涉及文件**：`services/llm.py`（prompt 加引用纪律）、`core/verify.py`（抽查）
**依据**：textbook-to-note 引用纪律（"Cite or it didn't happen"）/ 769仓精读版 §🅵 来源账本（claude-obsidian / transcript-critic）

### D5 · [AI推断] 标注（区分原话 vs AI 补充）

**目标**：AI 补充超出视频的内容显式标 `[AI推断]`，与视频原话区分。AI 不会把"自己编的"当"原话"，越讲越飘。

**具体改动**：
- `services/llm.py` 重排 prompt 要求：AI 自加内容（背景/延伸）标 `[AI推断]`；原文照搬不标
- orchestrator 收集推断点数量并报告（供人工抽查）

**验收标准**：
- [ ] 输出含 [AI推断] 标记（当 AI 有补充时）
- [ ] 视频原话与 AI 补充可明确区分

**涉及文件**：`services/llm.py`、`services/orchestrator.py`
**依据**：textbook-to-note inferred 标注 / obsidian-wiki 三档置信度 / 769仓精读版 §🅵

### D6 · confidence 实际落值（含核验人）

**目标**：frontmatter 的 `confidence` 从"空字段"变"真值"——AI 对每篇评估 high/medium/low + 核验状态。AI 知道哪篇没把握，重点抽查。

**具体改动**：
- `services/llm.py` 生成时自评 confidence（按内容与转写吻合度）
- 视频原句核对的标 `verified: human/auto`（参考 okf-skills trust tier：unverified / machine-confirmed / human-reviewed）
- `core/verify.py` 校验 confidence 非空

**验收标准**：
- [ ] frontmatter confidence 非空（high/medium/low）
- [ ] 有 verified 字段（来源核验状态）
- [ ] 低置信篇自动进"人工抽查清单"

**涉及文件**：`configs/note_style_spec.yaml`、`services/llm.py`、`services/orchestrator.py`
**依据**：student-llm-wiki confidence + 衰减 / okf-skills trust tier / 769仓精读版 §🅵 三档置信度

### D7 · 概念页（一概念一页，跨讲累积）

**目标**：核心概念独立成页（`concepts/隐马尔可夫模型.md`），统一定义跨讲累积。AI 教到该概念时读一页就全，不靠各讲碎片拼。

**具体改动**：
- 新增"概念抽取"（core `concepts.py`）：扫描课程笔记抽核心概念 → 生成概念页（定义 + 出现讲次 `[[链接]]` + 关系）
- 概念页可人工维护，AI 按需读（类比 student-llm-wiki `wiki/concepts/`）

**验收标准**：
- [ ] 核心概念有聚合页（覆盖课程主要概念）
- [ ] 概念页含出现讲次链接 + 统一定义

**涉及文件**：新增 `core/concepts.py`、`services/orchestrator.py`
**依据**：student-llm-wiki `concepts/`（最核心价值："跨课程连接是整个 wiki 最有价值的输出"）/ v7 §二缺点

### D8 · 极简词法检索（零依赖，不引向量库）

**目标**：AI 能"找"知识点而非"全读"——极简关键词搜索（frontmatter + 标题 + 正文词法匹配）。先不引向量库（轻架构）。

**具体改动**：
- 新增极简检索脚本（纯 Python 标准库）：关键词 → 返回匹配笔记 + 定位段落 + 相关度排序
- 按需嵌入 orchestrator 或独立 CLI；量大再评估 SQLite FTS5 过渡（769仓精读版 §五 参考 5）

**验收标准**：
- [ ] 输入关键词返回相关笔记 + 定位段落
- [ ] 零外部依赖（纯 Python 标准库可跑）

**涉及文件**：新增 `core/search.py`（或 `tools/search.py`）
**依据**：OKFy 确定性词法检索（`search_concepts` 零 embedding）/ 769仓精读版 §五 参考 5（SQLite FTS5 轻量过渡）

---

## 🔁 实施顺序与依赖

```
A1（改 spec + prompt + 实测）→ 独立，先做
A2 + A3（chunk 段落切 + assemble 定位）→ 一起做，改 core
  └→ 跑 41+165 回归（防破坏）
D1 + D2（总索引 + 互链）→ 紧随 A 之后，产出达标才有内容可编地图
D3（关联字段）→ 与 D2 同步做（字段 = 链接目标）
D4 + D5 + D6（条目引用 / AI推断 / confidence）→ 结合 A1 产出标准一并固化
B1（git）→ B2（语义对账）→ B3（断点）→ B4（低置信）
C1（解析实测）→ C2（git 分支）→ C3（其余）
D7（概念页）→ 课程笔记到量后再做（先有"出现讲次"才聚合）
D8（词法检索）→ 最后，量够再做
每完成一项：4 轮审核（完成度/回归/隐蔽缺陷/质量）+ 证据单
```

## 🚨 风险与回退

- A1 可能引入更长 prompt / 更多 token → 用户不在乎 token，接受
- A2 段落切可能让单块变小增多 → 可调 max_chars
- D1 索引生成依赖"A 产出稳定结构" → D 排在 A 之后做，结构不稳不编地图
- D2 互链可能产生悬空链接（指向不存在讲次）→ 生成时校验目标存在，缺目标标 warning 不报错（OKFy 约定）
- D5 [AI推断] 依赖 AI 自觉标注 → prompt 强制 + D4 条目引用兜底
- D7 概念页可能生成不准（概念抽取是难点）→ 核心概念先人工圈定，AI 补全
- B1/B2 涉及 git/GLM 依赖 → 失败不阻断主流程（降级）
- 每项改动前确保 41+165 全绿，改动后回归
