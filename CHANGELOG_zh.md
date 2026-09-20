# Changelog（简体中文）

<p align="center"><a href="CHANGELOG.md"><kbd>🇺🇸 English</kbd></a> · <kbd>🇨🇳 中文</kbd></p>

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与
[Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [0.4.3-os] - 2026-09-20

### Added

- **首次开源发布**：由内部 `md-rewrite-engine` 代码库整理而来——全量隐私清洗
  （内部路径/项目名/供应商细节零残留）、双语 README 与 CHANGELOG（英/中）、
  AGPL-3.0 + 商用双许可、CONTRIBUTING / CODE_OF_CONDUCT / SECURITY、路线图、打赏码。
- 测试资产入库：`tests/exhaustive/s2_exhaustive.py`（137 用例全 mock）+ 169 单元测试。
- `scripts/toc_gen.py` 由内部 temp 工具转正。

### Changed

- docs/ 整理：用户向手册留在顶层；内部计划与验收报告归档至 `docs/archive/`。

## [0.4.3] - 2026-08-23

### Fixed

- **gate_check 机械对账对文件名元数据误报**：源 clean.md 标题含日期/视频ID（如 `2026-06-30`、19 位抖音ID），被当"必须保留的硬数字"，重排丢弃后误报缺失（实测半吊子图集 20% 假 FAIL）。修复：`core/verify.py` `extract_keypoints` 跳过 ≥10 位纯数字（ID/哈希）；`scripts/gate_check.py` 加 `_clean_meta` 剥离日期（`YYYY-MM-DD`）。实测半吊子图集 20% → **PASS**，WSL v4 不受影响。测试 +2（超长ID跳过 / 日期剥离）。

## [0.4.2] - 2026-08-20

### Changed

- **内部一致性修复（根治改新没清旧）**：
  - `configs/note_style_spec.yaml`：剔 `traceability: per_claim`（与"知识库+留白/不强标出处"冲突）→ optional；`services/llm.py` 删溯源死代码。
  - `configs/user_prefs.yaml`：费曼密度改 `feynman_density.general: 2`（示范角度数，删旧 10/8/6 题数）；`scripts/gate_check.py` 加 `_feynman_min()` 从配置读（不再硬编码 `_FEYNMAN_MIN=2`）。
  - `docs/orchestration-manual.md` 第 10 步定稿"源数据外置 = 工作流输入原文全文（clean.md 含画面切片）"。
  - `configs/executors.yaml`：标注 anthropic 为"未启用/预留"备选，脚本全自动路径未验证。

### Fixed

- **4 处内部不一致**：① traceability 与留白冲突 ② 密度分档空转（10/8/6 未用）③ 源数据外置对象不明 ④ anthropic 脚本路径未验证未标注。
- **gate_check 费曼计数双计 bug**：`_FEYNMAN_MARK` 同时匹配圈数字与"（复述/类比…）"，一条"①（复述）"被算 2 → 每点"≥2"虚宽成"≥4"，配置驱动被掩盖；改为只数圈数字，实测 general=3 → v4 报 23 点不足。

### Security

- 维持：API Key 走环境变量，无新增依赖。

## [0.4.1] - 2026-08-19

### Added

- **打回闭环落地（本体主控）**：`scripts/gate_check.py`——门禁一键检查（输入笔记.md+原文.md，自动抽 🎤 语音作对账基准；输出机械对账数字覆盖率 / 6 件套完整度 / 费曼示范计数 / --score GLM 评分，PASS/FAIL+问题清单，退出码 0/1）。
- **编排手册强制闭环**：`docs/orchestration-manual.md` 第 7-8 步改为"重排 → 跑 gate_check → 不达标带问题清单针对性修补 → 再验 ≤4 次 → 挂起"，通过 = gate_check 全绿，不靠自觉。
- P1 加"每知识点交付前自检 6 件套"；P4 质检加"只报素材内真问题，不报素材外增强建议"。
- 测试：`tests/scripts/test_gate_check.py` 12 用例 + S2 穷举 8 用例（gate_check 路径/边界/终点一致性）。

### Changed

- `docs/orchestration-manual.md` 第 7-8 步（打回闭环从"自觉判断"改为"机器门禁"）。
- `services/llm.py` P4 质检降噪（只报素材内问题）。

### Fixed

- **打回闭环未落地**：v0.3.0 阶段 5 设计机制存在但本体主控路径从未实际执行——现由 gate_check + 强制步骤落地，v4 实测 FAIL→PASS。

### Security

- 维持：API Key 走环境变量，无新增依赖。

## [0.4.0] - 2026-08-18

### Added

- **篇内目录 TOC（新功能）**：`core/toc.py`（纯算法：从标题结构自动生成 `## 📑 本篇目录`，幂等、零依赖、跳过文档主标题）；`services/orchestrator.py` 的 `write_output` 落盘前自动插入 TOC（AI/本体无需手写，确定性机械活交代码）；`configs/note_style_spec.yaml` structure 新增 `toc` 栏；CLI 工具 `scripts/toc_gen.py`（手动批量用）。
- **两级目录体系完整**：课程级 `index.md`（D1，已有）+ 篇内 TOC——AI 无论先读课程还是单篇都不迷路。
- 测试新增 11 个 TOC 用例（提取/幂等/主标题排除/边界），全量 **145/145** + S2 **115/115** 全绿。
- **重排产出标准（知识库 + 教学留白，新定位）**：`configs/note_style_spec.yaml` 费曼由"每知识点 10 道"改为"2-4 道示范角度"；`docs/prompt-family-p1-p5.md` + `services/llm.py` 的 P1/P2 定位改为"**知识完整 + 教学留白**"——6 件套完整保留（知识不缺）、费曼每点 2-4 道示范（教学线索，非写满讲稿）、不强标时间戳出处（示例具体准确即可）；**逐字校对并入 P2 自查第一步**（抄写员视角核对命令/专名/数字/错别字，防"意图脑补"把错字看对）。
- **机械对账重定位（补丁）**：`core/verify.py` `extract_keypoints` 聚焦事实关键点（去中文提取，中文概念交 AI 语义对账；数字 ≥2 有效位滤 ASR 单数字噪声）；`reconcile` 数字**硬判定**（含合并匹配 `300 0`→`3000`）+ 英文缺失降级 **warnings 软提示**（不判不通过）→ 门禁在 ASR/重排场景从 11.9% 死锁修复为 93.8% 通过。
- **P4/P5 适配知识库+留白（补丁）**：`services/llm.py` `build_quality_prompt` 维度改为知识完整/事实准确/教学线索/结构可定位；`build_scoring_prompt` 标准改为 90+/70-89/<70 三档（非 95 详细度）。
- **重排即智能清洗（补丁）**：P1 + `build_rewrite_prompt` 加"顺带清洗"——按上下文纠正 ASR 错听/拆数字（mic→Mac、无斑图→Ubuntu、300 0→3000），不靠词典。

### Changed

- `write_output` 输出笔记时自动插入篇内目录（幂等：已有 TOC 跳过）。
- `configs/note_style_spec.yaml` `feynman_per_kp` 由 10 改为 2-4；引用纪律 D4 弱化为"示例具体准确、不强制标时间戳出处"。
- `docs/directory-contract.md` 更新至 v2.1（core 新增 toc.py）。

### Security

- 维持：API Key 走环境变量，无新增依赖，仅提交 `.env.example`。

## [0.3.0] - 2026-08-16

### Added

- **执行者选择器（阶段 1）**：`configs/executors.yaml` + `providers/executors.py`——4 环节（rewrite/reconcile/quality_check/scoring）独立配执行者（claude 本体 / glm / deepseek / anthropic），可混合；provider/model 优先级链：环境变量 > executors.yaml > models.yaml > 内置默认。
- **本体主控能力函数库（阶段 2）**：`services/orchestrator.py` 新增 `assemble_chunks`（物理分块兜底）/ `concept_map`（概念地图候选）/ `chunks_with_context`（逐块后文预告）/ `write_output`（笔记落盘 + 转写外置源文件）；`docs/capability-functions.md` + `docs/orchestration-manual.md`（10 步编排）。
- **本体主导全局（阶段 3）**：概念地图先行（Task-08）+ 逐块带"全局地图/前文摘要/后文预告/块间重叠"防隔离。
- **提示词家族 P1-P5（阶段 4）**：P1 本体重排（详细展开/少删/口语可丢/事实保留/6 件套/费曼 4 角度/schema 结构）、P2 自查、P3 概念对账、P4/P5 GLM 质检/评分已代码化（`services/llm.py`），文档 `docs/prompt-family-p1-p5.md`。
- **验证打回闭环（阶段 5）**：`core/verify.py` 新增 `gate()` fail-closed 门禁（机械对账/质检/评分任一不达标不能"通过"）；每块独立 4 次修补额度，超限挂起待人工；打回 = 带问题清单回 P1 针对性修补（反馈累积）。
- **使用手册**：`docs/user-guide.md`（怎么跑/配执行者/换执行者/换会话复用）。
- **S2 穷举脚本**：`tests/exhaustive/s2_exhaustive.py`（115 用例，7 块覆盖，全 mock）。

### Changed

- 打回重写逻辑：`process` 由"整块重做"改为"带问题清单针对性修补"；`max_rewrite_retries` 负数 clamp 到 0（至少跑 1 轮验证）。
- `resolve_model` 未知环节 key 回落 `_DEFAULT_MODELS["rewrite"]`（不再返回空串）。

### Fixed

- `resolve_model` 未知 key 返回空串 → 回落 glm-4.5-air（杜绝空模型名发请求）。
- `process` 负 `max_rewrite_retries` 静默跳过全部验证 → clamp 到 0，fail-closed 不被绕过。

### Security

- 维持：API Key 走环境变量，模型名/路径走 configs，仅提交 `.env.example`。

## [0.2.0] - 2026-08-14

### Added

- **A2 段落边界切**：`core/chunk.py` 按空行段落边界切分（无标题流水账不切半句；单段超长才字符硬切兜底）。
- **A3 无标题定位**：`core/assemble.py` 保留段落空行（A2 依赖）+ 无标题返回 1 根块不建假树。
- **D1 总索引**：`core/md_index.py` + `cli --index`（OKF 风格 index.md：okf_version/讲次地图/统计）。
- **D2 互链规范+校验**：spec linking 段 + prompt 互链 + `cli --validate-links`（悬空链接检测，缺目标 warning）。
- **D3 frontmatter 关联字段**：spec relation_fields（prerequisites/next/related）+ 校验。
- **D4 条目级引用纪律**：prompt 强制示例标出处 + `find_missing_source` 抽查。
- **D5 [AI推断] 标注**：prompt 强制标注 + process `inferred` 计数。
- **D6 confidence 落值**：spec confidence_policy + `validate_confidence` + 低置信篇自动进人工抽查清单。
- **D7 概念页**：`core/concepts.py` + `cli --concepts`（一概念一页跨讲聚合，粗体术语抽取）。
- **D8 词法检索**：`core/search.py` + `cli --search`（零依赖关键词检索）。
- **B1 git 自动提交**：`providers/git_io.py`，产出（重排/索引/概念页）落盘自动 add+commit。
- **B2 语义对账**：概念级覆盖核对（`run_reconcile`，检出词级漏掉的同义改写缺失）。
- **B3 断点续跑**：state 文件（每单元进度 + 完成态缓存），输入 mtime 变化自动失效。
- **B4 低置信标记**：prompt 标注 + process `low_conf` 计数。
- **C2 git 分支保护**：process `branch` 参数（重排前建 rewrite-分支 + diff 预览）。
- **C3a 增量批处理**：`process_course`（按 mtime 只处理变更笔记）。
- **C3b 改动理由**：prompt 要求删除/修改附说明行。
- **C3d frontmatter schema 校验**：`validate_frontmatter_schema`（必填/类型，core 零依赖）。
- 测试从 41 扩到 **133 用例**（新增 92）。

### Changed

- `configs/note_style_spec.yaml` v1.2 → **v1.3**（linking / relation_fields / confidence_policy）。
- `configs/models.yaml` 新增 `reconcile` 档位；**模型分工**：rewrite/reconcile 走 Claude 通道（anthropic 协议），quality_check/scoring 走 GLM（glm-4.5-air）。
- `providers/llm_client.py` 新增 `anthropic` 供应商（Anthropic Messages 协议，走 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`）；修正 provider 路由（quality_check/scoring 明确走 GLM，不再误找 DeepSeek key）。
- process 返回新增 `inferred / low_conf / diff / resumed` 键；失败模式返回键集统一。

### Fixed

- **BOM 文件首个标题丢失**：`read_md` 去除 UTF-8 BOM（记事本默认）。
- **process 失败模式键集不一致**：文件不存在/空内容/LLM 异常统一返回契约。
- **cli 模式顺序缺陷**：`--validate-links`/`--concepts` 无 input 时被误拦。
- **断点缓存不检测输入变化**：state 记录 `src_mtime`，输入变自动失效。
- **点号术语未提取**：`**HMM 2.0**` 等正则字符类加 `.`。
- **providers 测试从未运行**：`tests/providers/` 补 `__init__.py`（test_file_io/test_llm_client 首次实际运行），并同步 2 处过期模型断言。

### Security

- 维持：API Key 走环境变量，模型名/路径走 configs，仅提交 `.env.example`。

## [0.1.0] - 2026-08-13

### Added

- 项目骨架：按《目录契约》新建 `configs/ core/ services/ providers/ scripts/ tests/ docs/`
  （核心域零外部依赖，单向依赖 `cli → services → core+providers+configs`）。
- **流水线核心**：
  - `core/assemble.py`：清洗后 md → 标题树/面包屑（支持 `#` 标记 + 无标记"第X章" + 白名单词）。
  - `core/chunk.py`：机械粗切（每块 ≤ max_chars + 块间重叠防切半句 + 面包屑 + 超长单行硬切）。
  - `core/rewrite.py`：AI 滚动编译调度（窗口滚动 + 前文摘要贯穿 + AI 边界合并）。
  - `core/verify.py`：语义对账（关键点覆盖率检出缺失）+ 质量评分 + check 组合。
- **LLM 适配**：
  - `providers/llm_client.py`：GLM/DeepSeek OpenAI 兼容封装（模型名从配置读、环境变量覆盖、超时/重试、4xx 不重试）。
  - `services/llm.py`：三种 prompt（重排/质检/评分），AI 输出 best-effort JSON 解析（含裸换行修复）。
  - `services/orchestrator.py`：主流程编排（读→切→滚动重排→验证→写），不合格打回重写 + LLM 评分门槛。
- **命令行**：`cli.py`（薄层入口，防呆：非法参数/负值报错，`--json` 供集成）。
- **规范**：`configs/note_style_spec.yaml` v1.2（继承 v1.1 8 字段 + OKF 加 confidence/sources/status/wikilinks）。
- **视频线组装参考**：转写侧产出半成品 md 的思路以脚本形式实现（不侵入本引擎主流程）。
- **测试**：tests/ 全量 41 用例（core/services/providers 镜像结构，`python -m unittest discover -s tests -t .`）。

### Fixed

- `core/assemble.py`：纯空白输入返回空列表（不再产生空根块）。
- `core/assemble.py`：移除纯数字小节自动识别（3.14/年份/版本号误判），规则宁漏勿误，数字小节交 AI 滚动兜底。
- `core/chunk.py`：超长单行按字符硬切防超限；首个 chunk 不再误标 overlap。
- `services/llm.py`：AI 输出 JSON 含裸换行时自动修复再解析（best-effort）。

### Security

- API Key 一律走环境变量（`GLM_API_KEY`/`DEEPSEEK_API_KEY`），无硬编码。
- 模型名/路径一律走 `configs/` 或环境变量，无硬编码绝对路径。
- 仅提交 `.env.example`，禁止真实 `.env` 入库。
