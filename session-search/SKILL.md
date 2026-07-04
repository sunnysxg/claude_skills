---
name: session-search
description: >
  检索已归档的历史 agent session 摘要（关键词、项目、时间、未竟事项）。
  用户指向上次/最近的 agent 工作（最近的 session、上次那个 chat、接着上次、哪次改过），
  且 CLAUDE.md、README、_sxg/ 等项目文档不足以回答时，先查归档再答。
  仓库文档或源码能直接回答的问题、与历史 session 无关的新任务、handoff 交接待办，不用本 skill。
---

# Session Search — 检索历史 session 摘要

续接**上次 agent 工作**或找「哪次 chat 做过 X」，但项目文档说不清时用。归档目录与文件格式见
[references/archive-layout.md](references/archive-layout.md)。

归档按机器独立（`~` 各自解析），本 skill 只搜**本机**归档。

## 0. 何时用 / 何时不用（先判断再搜）

**用** — 同时满足：

- 用户话里指向**历史 agent 行为**（最近的 session、上次改的那个、之前 agent 做的、接着上次、哪次改过 X）
- 快速扫过 `CLAUDE.md`、README、`_sxg/` 后，仍缺「谁什么时候做了什么、还有什么未竟」

**不用**：

- 代码/配置怎么用，文档或源码里能直接找到
- 纯新需求，与历史 session 无关
- 要 **handoff** 给下个 agent → 用 `/handoff`

**流程**：文档不够 → 执行下面检索 → 简短交代「查了 session 归档」再答；无命中则直说，并建议 `/session-log` 补记录。

## 1. 解析查询

从用户话里提取（缺省则不过滤）：

| 维度 | 示例 | 用法 |
|------|------|------|
| 关键词 | mlflow、gitlab、lineage | grep 正文 + frontmatter |
| 项目 | quantalpha、factor_infra | 文件名中的 `{project}` 段或 `project:` 字段 |
| 时间 | 上周、260629、6 月 | 文件名时间戳前缀或 index 日期列 |
| 意图 | 「上次」「最近」「哪次」 | 多命中时按时间新→旧；「最近/上次」默认取最新 1 条 |

项目名不确定时：从 cwd / 用户 `@` 路径推断默认项目；隐式触发时**优先筛当前项目**，无命中再扩全局。

## 2. 检索顺序（先广后窄）

**Step A — index 快扫**

读 `~/_sxg/llm_session_log/index.md`，按摘要 / Session 标题 / 项目列做第一轮匹配。

**Step B — 文件名过滤**

```bash
LOG=~/_sxg/llm_session_log
ls "$LOG"/*_{project}_*.md 2>/dev/null       # 新格式，按项目筛
ls "$LOG"/\[{project}\]*.md 2>/dev/null      # 旧格式（存量文件，主要在集群）
ls "$LOG"/*.md
```

文件名两代格式都可能存在，见 archive-layout.md；内容 grep 不受格式影响。

**Step C — 内容 grep**

```bash
rg -i -l '关键词1|关键词2' "$LOG" --glob '*.md' --glob '!index.md' --glob '!INDEX.md'
rg -i '关键词' "$LOG" --glob '*.md' -n -C 0
```

同时搜 frontmatter 字段：`keywords`、`summary`、`session_title`、`suggested_chat_title`、`git_commits`。

**Step D — 读命中文件**

对每个候选（通常 ≤5 个）读 YAML frontmatter + 「完成事项」「未竟 / 下次继续」节。不要编造未读内容。

## 3. 回复格式

用简体中文，结构如下：

```markdown
## 检索：{用户原问简述}

找到 N 条相关 session（按时间新→旧）：

### 1. {session_title} — {date} {time}
- **项目**：{project}
- **文件**：`~/_sxg/llm_session_log/{filename}`
- **Chat 标题建议**：`{suggested_chat_title}`（在 chat 历史里可搜此名）
- **匹配原因**：{为何命中，1 句}
- **要点**：{2–4 条 bullet，来自摘要}

### 2. …

---
未找到时：说明搜了哪些词/项目；建议换关键词或 `/session-log` 补归档。
```

规则：

- 最多详述 **5** 条；更多只列 index 一行
- 给出**可点击的完整路径**
- 若用户问「上次/最近」，默认只展开**最新 1 条**并简述其余
- **隐式触发**时：先 1 句交代「查了 session 归档」，再答用户原问题；不必每次贴完整模板
- 不要继续写无关代码，除非用户接着提新任务

## 4. 与 session-log / handoff 的边界

| 工具 | 用途 |
|------|------|
| **session-search**（本 skill） | 找**已归档**的历史 session |
| **session-log** | 关 chat 前**写入**新摘要 |
| **handoff** | 给下一个 agent 的待办（不是检索） |

归档为空或太旧时，告知用户用 `/session-log` 养成关 session 前记录的习惯。

## 5. 参考

文件名与 frontmatter 标准见 [references/archive-layout.md](references/archive-layout.md)（与 `session-log` 共用约定）。
