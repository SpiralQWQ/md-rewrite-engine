# 解析底座实测报告（R1 选型）· 2026-08-14

> **问题**：`core/assemble.py` 是否替换为现成解析器（arborparser vs markdown-it-py）？
> **方法**：真实"复杂 md（标题/表格/代码块）+ 无标题 md"跑两库对比。

## 一、实测结果

| 能力 | markdown-it-py 4.2.0 | arborparser |
|---|---|---|
| `#` 标题识别 | ✅（h1/h2 token） | ❌（非通用 md 解析） |
| 表格 | ⚠️ 需 `js-default` 预设（`commonmark`/默认 不含） | ❌ |
| 代码块 | ✅（fence token） | ❌ |
| 无标题编号（第一章/1.1/罗马） | ❌（当普通段落） | ✅（专长：章节编号体系） |
| 无标题流水账段落切 | ❌（无段落语义） | ❌ |
| 定位 | 通用 Markdown tokenizer | **章节编号识别器**（非 md 解析器） |
| 依赖/API | 轻量，需预设调表格 | API 学习成本高（ChainParser+PatternBuilder） |

## 二、关键洞察

1. **两者都不完整覆盖我们的场景**：无标题 md 的段落切（A2）两库都不支持——这是 assemble.py 已实现的独特能力。
2. **arborparser 与 assemble 的 `_ORD_HEADING`（第X章/第X讲 正则）功能重叠**——它是"编号识别"专用，不是通用解析器。
3. markdown-it-py 的表格支持需 `js-default` 预设，且我们输入（清洗后教学文本笔记）表格/代码块占比低。

## 三、结论（R1）

> **维持自研 assemble，不引入新解析器。**

**理由**：
1. assemble.py 已实现：`#` 标题 + 无标记序号（第X章/第X讲）+ 白名单词 + 代码块/HTML注释/$$公式内 `#` 保护 + **段落边界保留（A2 无标题流水账段落切）**——覆盖全部核心场景。
2. 目录契约 **core 零依赖铁律**：引入外部解析器破坏纯算法定位。
3. arborparser 编号识别与既有 `_ORD_HEADING` 重叠，引入纯增依赖。
4. markdown-it-py 的表格/代码块 token 对教学文本收益有限。

**候选保留**：markdown-it-py（已装，`js-default` 预设）作为"未来需要完整 md AST（表格/嵌套结构）"时的升级路径。

## 四、影响

- 无生产代码改动（assemble 维持自研）。
- requirements.txt 不新增 arborparser（实测用，不引入运行时依赖）。
