> ⚠️ **已归档**：本文档为历史版本快照（v0.2.0），内容不更新；最新状态见 `../README.md` 文档表 + `CHANGELOG.md`。
# 修正计划 V3 · 施工 Task 清单（fixloop S1 穷举闭包）

> **依据**：`docs/修正计划_20260814.md`（v3）+ `~/.claude/spec/_exhaustive_test_charter.md`（fixloop 规范）
> **执行规则**：逐 Task 执行 → 每个 Task 完成立即 4 轮深度审核（完成度 / 回归影响 / 隐蔽缺陷 / 质量设计）→ 全过才进下一个；任一轮发现问题 → 修复 → 重走 4 轮。
> **证据单**：每轮修复写 `temp/fixloop_evidence/round_N.md`（问题现象 / 根因 / 核心修复 / 影响面）。
> **顺序**：阶段 A → D → B → C（A1 已完成，纳入回归）。
> **共 47 个 Task + 穷举环节（S2）+ 最终验收（S4）+ CHANGELOG（S4）**。

---

## 阶段 A · 产出质量（P0）— 治"无标题乱切"根因

| Task | 内容（最小可验证单元） | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-01 | A2：改造 `core/chunk.py` 的 `_split_lines_by_chars`——优先按**空行段落边界**切分，仅当**单段超长**（>max_chars）才字符硬切兜底 | 无标题流水账每块不含"半句话"；单段超长才硬切；有标题仍按标题切 | `core/chunk.py` |
| Task-02 | A2：补 `tests/core/test_chunk.py` 段落边界测试 | 新增用例覆盖：段落边界切 / 单段超长硬切 / 有标题回归 / 空行连续 / 单段恰等于 max_chars | `tests/core/test_chunk.py` |
| Task-03 | A2：全量回归 41+165 | 既有测试全过，无回归 | tests/ |
| Task-04 | A3：确认/微调 `core/assemble.py`——无标题 md 返回 1 个根块（level=1, title=''），不建假树、不崩 | 无标题 md → 1 根块；纯段落可被 Task-01 段落切处理 | `core/assemble.py` |
| Task-05 | A3：补 `tests/core/test_assemble.py` | 无标题不崩/不建假树 / 有标题正常建树（回归）/ 空输入 / 纯空白 / 纯段落可切 | `tests/core/test_assemble.py` |
| Task-06 | A3：全量回归 41+165 | 既有测试全过 | tests/ |

## 阶段 D · 内容结构补丁（P0/P1）— AI 看懂整门课

### D1 总索引 index.md（P0）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-07 | 新增 `core/md_index.py`——扫描课程目录全部笔记 frontmatter+标题 → 生成 `index.md`（讲次 `[[链接]]` + 一句话摘要 + 统计块 + `okf_version`） | 生成 index.md 含全部讲次链接+摘要；链接全部有效 | 新增 `core/md_index.py` |
| Task-08 | 集成：orchestrator 或独立 CLI 触发索引生成（A1 产出后统一跑） | 一条命令生成/更新课程索引 | `services/orchestrator.py` 或 `cli.py` |
| Task-09 | 补 tests（索引生成 + 死链检测） | 索引生成正确；死链被检出 | `tests/` |

### D2 [[链接]] 互链（P0）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-10 | `configs/note_style_spec.yaml` 加互链规范：前置知识/后继讲/相关知识点用 `[[讲次#知识点]]` | spec 含互链语法约定 | `configs/note_style_spec.yaml` |
| Task-11 | `services/llm.py` 重排 prompt 加互链要求：提到前置概念自动加链接，重复概念用链接引用而非重写 | prompt 强制互链；重复概念不重写 | `services/llm.py` |
| Task-12 | `core/verify.py` 加链接校验：链接目标存在；缺目标标 warning 不报错（OKFy 约定） | 悬空链接被检出并 warning；不阻断 | `core/verify.py` |
| Task-13 | 补 tests（互链语法 / 悬空链接 / 校验不崩） | 用例覆盖上述 | `tests/` |

### D3 frontmatter 关联字段（P1）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-14 | `note_style_spec.yaml` frontmatter 增 `prerequisites / next / related`（v1.2→v1.3） | spec 含 3 新字段定义 | `configs/note_style_spec.yaml` |
| Task-15 | `services/llm.py` prompt 要求按实际内容填 3 字段 | prompt 强制填写 | `services/llm.py` |
| Task-16 | `core/verify.py` 校验 3 字段非空且指向存在、与 D2 链接一致 | 字段可机器校验；与互链同步 | `core/verify.py` |
| Task-17 | 补 tests | 用例覆盖 | `tests/` |

### D4 条目级引用（P1）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-18 | `services/llm.py` prompt 加引用纪律：示例/原句标 `(来源: 第X讲 HH:MM)` 或 `(来源: 第X页)` | prompt 强制条目级出处 | `services/llm.py` |
| Task-19 | `core/verify.py` 出处抽查辅助（统计缺出处条目） | 可抽查出处缺失 | `core/verify.py` |
| Task-20 | 补 tests | 用例覆盖 | `tests/` |

### D5 [AI推断] 标注（P1）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-21 | `services/llm.py` prompt 要求 AI 自加内容标 `[AI推断]`；原文照搬不标 | prompt 强制标注 | `services/llm.py` |
| Task-22 | `services/orchestrator.py` 收集推断点数量并报告 | 返回 low_conf/inferred 统计 | `services/orchestrator.py` |
| Task-23 | 补 tests | 用例覆盖 | `tests/` |

### D6 confidence 落值（P1）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-24 | `note_style_spec.yaml` 加 confidence/verified 落值规范（high/medium/low + verified 状态） | spec 含字段 + trust tier 说明 | `configs/note_style_spec.yaml` |
| Task-25 | `services/llm.py` prompt 要求自评 confidence + verified | prompt 强制填写 | `services/llm.py` |
| Task-26 | `core/verify.py` 校验 confidence 非空 | 空 confidence 被检出 | `core/verify.py` |
| Task-27 | `services/orchestrator.py` 低置信篇进"人工抽查清单" | 返回 low_conf 列表 | `services/orchestrator.py` |
| Task-28 | 补 tests | 用例覆盖 | `tests/` |

### D7 概念页（P1）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-29 | 新增 `core/concepts.py`——扫描课程笔记抽核心概念 → 概念页（定义 + 出现讲次 `[[链接]]` + 关系） | 核心概念有聚合页 | 新增 `core/concepts.py` |
| Task-30 | 集成 + 补 tests | 概念页生成正确；覆盖出现讲次链接 | `services/orchestrator.py`、`tests/` |

### D8 极简词法检索（P2）
| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-31 | 新增 `core/search.py`——零依赖关键词检索（frontmatter+标题+正文词法匹配 → 返回笔记+段落+排序） | 输入关键词返回相关笔记+段落；纯 stdlib 可跑 | 新增 `core/search.py` |
| Task-32 | 补 tests | 用例覆盖空/超长/无匹配/中文 | `tests/` |

## 阶段 B · 工程增强（P1）— 准确稳定骨架

| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-33 | B1：orchestrator 每次 write_md 前 git add+commit（带 Task+时间 message）；目标不在 git 仓库则跳过不阻断 | 3 步重排 → 3 次 commit；`git log` 可回溯 | `services/orchestrator.py`、`providers/file_io.py` |
| Task-34 | B1：补 tests（fake git / 非 git 目录跳过） | 用例覆盖 | `tests/` |
| Task-35 | B2：`core/verify.py` 加 `semantic_reconcile()` 接口 + `services/llm.py` GLM 语义对账调用（概念覆盖核对，非词级） | 能检出"词级对账漏掉但概念级缺失"（如 STAR法则→四段式） | `core/verify.py`、`services/llm.py` |
| Task-36 | B2：集成 orchestrator + 补 tests | 语义对账接入验证链路 | `services/orchestrator.py`、`tests/` |
| Task-37 | B3：orchestrator 断点续跑——每单元完成写状态文件；重跑读状态跳过已完成 | 模拟中断 → 重跑 → 跳过已完成单元，输出与一次跑完一致 | `services/orchestrator.py`、状态文件 |
| Task-38 | B3：补 tests（状态文件读写 / 中断重跑终点一致） | 用例覆盖 | `tests/` |
| Task-39 | B4：`services/llm.py` prompt 要求存疑处标 `[低置信]`；orchestrator 收集 low_conf 列表 | 输出含 [低置信] 标记；返回 low_conf 列表（与 D5/D6 协同） | `services/llm.py`、`services/orchestrator.py` |
| Task-40 | B4：补 tests | 用例覆盖 | `tests/` |

## 阶段 C · 选型落地（P2）

| Task | 内容 | 验收点 | 涉及文件 |
|---|---|---|---|
| Task-41 | C1：装 arborparser + markdown-it-py，拿真实"复杂 md（表格/公式）+ 无标题 md"跑对比 → 出实测报告 → 定 R1 | 实测报告：哪个对复杂结构准、哪个对无标题支持好 | 实测脚本 + `docs/解析底座实测报告.md` |
| Task-42 | C1：按 R1 结论集成 `core/assemble.py`（如确认引入则替换/补充解析层；否则记录决策不引入） | assemble 解析能力与 R1 一致 | `core/assemble.py` |
| Task-43 | C2：orchestrator 重排前 `git checkout -b rewrite-<ts>` + 产出后 diff 摘要；可 `git checkout master` 回滚 | 重排前自动建分支；diff 可审；可回滚 | `services/orchestrator.py` |
| Task-44 | C3a：增量处理——只处理 mtime 变化的 md | 未变更 md 跳过 | `services/orchestrator.py` |
| Task-45 | C3b：删除/修改带理由报告 | 每次 AI 改动输出理由 | `services/llm.py`、`services/orchestrator.py` |
| Task-46 | C3c：评估引入 llm-wiki-compiler 利弊（npm）→ 出评估报告，维持自研或引入 | 评估报告结论明确 | `docs/重引擎评估报告.md` |
| Task-47 | C3d：jsonschema 校验 AI 输出结构（frontmatter + 栏目） | 不合规输出打回 | `core/verify.py`、`requirements.txt` |

---

## 穷举环节（S2）— 全部 Task 完成后执行

> 按 `_exhaustive_test_charter.md` 第一章：**路径穷举 + 边界严格 + 终点一致性** 三层。
> 对象：CLI 入口 + orchestrator 主流程 + 各 core 纯算法 + 全部新增模块（md_index/links/concepts/search/semantic/git/断点）。

- **路径穷举**：每个入口（CLI 参数组合 / 文件缺失 / 空文件 / 超长 / 二进制 / 编码 GBK-BOM-CRLF / 目录无写权限 / 非 git 仓库 / 断网超时 / 强杀重跑）→ 完整路径清单
- **边界严格**：非法输入 / 空值 / 边界值 / 超长 / 重复 / 回退 / 中断 / 并发 → 拒绝或提示，不崩不卡
- **终点一致性**：通向同一终点的路径分组比对（如"输出写文件"多入口、LLM 返回 None / 超时 / 异常 的失败模式终点一致；CLI `--json` 与普通输出的结果字段一致）
- **收敛判定**：high==0 && low<5 && medium<3 → 进最终验收
- 每轮发现写证据单 `temp/fixloop_evidence/round_N.md`

---

## 最终验收（S4）— 全部 Task + 穷举完成后

- **全量回归**：41+165 + 本轮新增测试全绿
- **终点一致性报告**：殊途同归终点分组比对，逐项一致
- **证据单核查**：`temp/fixloop_evidence/round_N.md` 齐全，均体现"现象/根因/核心修复/影响面"
- **验收报告**：写 `docs/验收报告_v0.2.0.md`（命名对齐版本；现有 `验收报告_v0.1.0.md` 为 v0.1.0 阶段）
- **CHANGELOG**：追加 `CHANGELOG.md`（Keep a Changelog + Semantic Versioning，Unreleased 段 + 0.2.0 版本段）

> 📌 报告位置待用户确认：验收报告 `docs/验收报告_v0.2.0.md` + CHANGELOG 追加 `CHANGELOG.md`（默认建议如上）。
