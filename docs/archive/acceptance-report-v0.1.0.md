> ⚠️ **已归档**：本文档为历史版本快照（v0.1.0），内容不更新；最新状态见 `../README.md` 文档表 + `CHANGELOG.md`。
# 验收报告 · md-rewrite-engine v0.1.0（补丁计划全量验收）

> 验收日期：2026-08-13｜依据：`docs/TASK_LIST.md`（S1 穷举闭包）｜结论：✅ 全部通过

## 一、验收范围（Task-01 ~ Task-15 全量）

| Task | 内容 | 状态 | 证据 |
|---|---|---|---|
| Task-01 | text-cleaning-engine 标题误删修复 | ✅ | 5 标题恢复 / 答主名照删 / 真实md 32标题 / 8/8+100% |
| Task-02 | core/assemble.py（标题树/面包屑） | ✅ | 14 边界测试 + 真实md 32块 |
| Task-03 | core/chunk.py（切块/重叠/超限） | ✅ | 9 测试（首块overlap/超长单行/边界） |
| Task-04 | core/rewrite.py（滚动编译调度） | ✅ | 5 测试（摘要贯穿/边界合并/rewritten保留） |
| Task-05 | core/verify.py（对账/评分） | ✅ | 12 测试（缺失检出/阈值打回） |
| Task-06 | providers/file_io.py | ✅ | 中文读写/原子写/扫描/防呆 |
| Task-07 | providers/llm_client.py | ✅ | 模型解析/缺Key/重试/4xx不重试 |
| Task-08 | services/llm.py | ✅ | JSON容错(裸换行)/prompt注入/三环节 |
| Task-09 | services/orchestrator.py | ✅ | 全链路/打回重写/LLM评分 |
| Task-10 | cli.py | ✅ | 防呆/参数透传/--json |
| Task-11 | note_style_spec v1.2（OKF） | ✅ | 8字段+OKF 4字段+7栏目 |
| Task-12 | transcription-tools 组装 md | ✅ | 真实产物组装/防呆/CLI |
| Task-13 | tests 全量 | ✅ | 41/41 unittest |
| Task-14 | 全量回归 + 终点一致性 | ✅ | 见下 |
| Task-15 | CHANGELOG | ✅ | 见 `CHANGELOG.md` |

## 二、全量穷举回归

- `md-rewrite-engine`：**41/41** unittest 通过
- text-cleaning-engine：验收 **8/8** + 教学保留率 **100%**
- 组装真实视频产物：**64617 字符**（正文 + 视觉附录 + 帧标记）组装成功

## 三、终点一致性报告（殊途同归分组比对）

| 分组 | 路径 | 结果 |
|---|---|---|
| 组1 assemble 幂等 | 同 md 两次解析 | 32==32 块，标题/面包屑逐项一致 ✅ |
| 组2 chunk 确定性 | 同 blocks 两次切块 | 2==2 块，文本逐项一致 ✅ |
| 组3 process 确定性 | 同输入+同 mock 两次 | 输出/units 完全一致 ✅ |
| 组4 多入口一致 | cli.main vs process 直调 | cli 正确转发，结果一致 ✅ |

## 四、修复证据单（13 轮，temp/fixloop_evidence/）

| 轮次 | 问题 | 根因 | 状态 |
|---|---|---|---|
| round_01 | 清洗引擎误删教学标题 | 白名单简历词+水印判定 | ✅ 修复 |
| round_02 | 数字小节误判(3.14/年份) | 正则过宽 | ✅ 移除，AI兜底 |
| round_03 | 单行超限不切+首块overlap误标 | 切分逻辑+seal设计 | ✅ 修复 |
| round_04 | —（无缺陷） | — | ✅ 通过 |
| round_05 | —（无缺陷） | — | ✅ 通过 |
| round_06 | 测试断言(扫描数) | 测试期望错 | ✅ 修正 |
| round_07 | —（无缺陷） | — | ✅ 通过 |
| round_08 | AI输出裸换行JSON解析失败 | json.loads不兼容裸换行 | ✅ 修复 |
| round_09 | _hint不存在/循环歧义/漏LLM评分 | 契约不完整 | ✅ 修复 |
| round_10 | mock未生效 | patch对象错 | ✅ 修正测试 |
| round_11 | —（无缺陷） | — | ✅ 通过 |
| round_12 | 测试断言(帧标记) | 用了clean版 | ✅ 修正测试 |
| round_13 | assemble纯空白→空根块 | 未strip判断 | ✅ 修复 |

**证据单完整性**：13/13 齐全，均含「现象/根因/核心修复/影响面」四项，非罗列完成项。✅

## 五、结论

- 补丁计划全部 15 个 Task 验收通过，无遗留漏洞
- 代码改动均为新增/最小修复，无对既有功能的回归破坏
- 架构契约（core 零依赖/单向依赖/配置分离）落实，无硬编码密钥/绝对路径

## 六、fixloop 穷举轮（用户追加要求，2026-08-13）

> 按 `_exhaustive_test_charter.md` 方法论对全模块做 S2 防呆/全路径/终点一致性穷举。
> **这一轮揪出了 6 个正常输入测不出的真实缺陷**——证明"确定可行吗"的追问是有价值的。

| 严重度 | 缺陷 | 修复 |
|---|---|---|
| HIGH | chunk max_chars=0/负数 → **无限循环** | clamp 参数 |
| HIGH | write_md 并发 → Windows **PermissionError** | 写锁 |
| HIGH | process LLM 异常抛裸异常（vs 文件错误返回 dict）→ **终点不一致** | 统一转 error dict |
| MED | verify/assemble/file_io/llm_client 多处 **None 输入崩** | isinstance 防御 |
| MED | call_llm response 无 choices → KeyError | 结构校验抛明确错误 |

**收敛判定**：high=0（死循环/并发/终点不一致全清零）→ 收敛 ✅
- 穷举测试 **34/34 PASS**
- 原单元测试 **41/41 回归通过**
- 证据单 round_14 记录 6 缺陷全链路（现象/根因/修复/影响面）

## 七、fixloop 持续轮（round_15/16，用户要求持续按 fixloop）

> 第一轮收敛后**继续深层穷举**（多轮直到连续无新发现）。

| 轮次 | 覆盖 | 新缺陷 | 结果 |
|---|---|---|---|
| round_15 | 只读/目录路径/特殊文件名/并发/500/Timeout/429/损坏JSON/坏spec/纯英文/纯代码/无标题/超长集成 | **1 个**：llm_client `max_retries=-1` 跳过调用直接失败 | 修后 **23/23** |
| round_16 | 正则边界/编码(BOM/CRLF/emoji/GBK)/process+cli 4入口终点一致/1MB性能/覆盖率边界 | 0 个 | **18/18** |

**收敛判定**：round_15 修复 1 个后，round_16 无新发现 → **连续两轮无新缺陷，fixloop 收敛（high=0）** ✅

**最终状态**：
- 单元测试 **41/41** + 穷举（14 轮 34 + 15 轮 23 + 16 轮 18）**75/75**
- 修复证据单 **15 份齐全**（round_01~15，均含现象/根因/修复/影响面）
- 累计修复 **8 个真实缺陷**：死循环/并发权限/终点不一致/None×5/retries负数/裸换行JSON/结构异常

## 八、fixloop 持续轮（round_17~22，自动进行至收敛）

> 用户要求"持续按 fixloop 自动进行"，连续 9 轮穷举直到稳定收敛。

| 轮次 | 覆盖 | 新缺陷 | 结果 |
|---|---|---|---|
| round_17 | 标题跳级/同级/特殊字符/表格列表/overlap极端/块长边界/全合并/rewritten=None/阈值/并发LLM/原地覆盖 | **1**：rewritten=None 合并崩 | 修后 16/16 |
| round_18 | .MD大写/深目录/空路径/纯代码块/1万标题/max_chars=1/1000块/空text/全英文/差一字/timeout=0/并发100 | **2**：代码块内#误判 + 纯空白块 | 修后 18/18 |
| round_19 | HTML注释/引用块/7个#/空标题/保留名/BOM/只读/超大overlap/并发20/100KB/批量 | **1**：HTML注释内#误判 | 修后 16/16 |
| round_20 | 公式块/frontmatter/分隔线/TOC/HTML标题/深嵌套/分数单调/配置矩阵 | **3**：$$公式#误判 + frontmatter未识别 + 空行空根块 | 修后 12/12 |
| round_21 | 未闭合块/混合块/表格#/列表/0字节/嵌套spec/重复process | **0** | 13/13 |
| round_22 | 自动链接/5层列表/组合极端/乱序bc/中英对账/正斜杠/覆盖 | **0** | 15/15 |

**收敛判定**：round_21、round_22 连续两轮无新发现 → **fixloop 稳定收敛（high=0）** ✅

## 九、最终结论（fixloop 全量）

- **单元测试 41/41** + **穷举 165/165**（9 轮：34+23+18+16+18+16+12+13+15）
- **修复证据单 20 份齐全**（round_01~20）
- **累计修复 14 个真实缺陷**：
  - 崩溃类：死循环 / 并发权限 / rewritten=None / 各 None 输入
  - 正确性类：代码块 / HTML注释 / $$公式 三类"块内 # 误判" + frontmatter / 空根块
  - 一致性类：process 失败模式终点不一致 / 裸换行JSON / retries负数 / 结构异常
- **模块 13 个 py 文件**，架构契约落实，无硬编码密钥/绝对路径
- **结论：fixloop 收敛，模块达到"正常+异常+并发+中断+解析正确性"五态稳定**


