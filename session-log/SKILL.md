---
name: session-log
description: >
  关闭 session 前，把本次对话的工作摘要归档到 ~/_sxg/llm_session_log/ 并更新索引，
  同时给出建议的 chat 标题。同一 chat 再次 log 时更新同一条，不新建重复条目。
disable-model-invocation: true
---

# Session Log — 关 session 前写摘要

用户要在**结束本次 chat 之前**留下可检索记录，避免「几天前改过什么但找不到对应 session」。
chat 侧边栏只能按标题/时间浏览，这个归档 + 索引是**刻意为之的可搜索层**；检索用
`session-search`，本 skill 只负责写入。

你的任务：**回顾当前对话**，写一份结构化 session 摘要到**全局归档目录**，并生成
`suggested_chat_title`。

> **平台**：时间解析（`session_times.py`）与 upsert（`session_resolve.py`）支持 Cursor 和 Claude Code；
> 脚本会自动识别 transcript 格式。存量回填（`session_backfill.py`）仍仅支持 Cursor。

## 0. 执行边界与效率

- session-log 只做归档；不要顺带 commit、补文档或重跑项目测试，除非用户明确同时要求。
- 第一轮并行收集 transcript 时间、Git 事实、template、index 和已有 target；不要逐项串行读取。
- `session_times.py` 返回 `fallback: false` 时直接采用，不再人工重扫 transcript。
- resolve 后集中写归档、更新 index、register 映射，避免为每个字段单开工具轮次。

## 1. 确定项目

按优先级：

1. 用户 `@` 的路径所在项目（含 `CLAUDE.md` 的子目录根）
2. 从 cwd 向上找最近的 `CLAUDE.md` 或 git 根
3. 多项目并列时，以**主要改动最多的那个**为准；不确定则问用户

记为 `{PROJECT}`（绝对路径）。元信息字段：

| 字段 | 取值 |
|------|------|
| `project` | 项目根目录名 snake_case 化：全小写、`-` → `_`（如 `quantalpha`、`factor_infra`） |
| `project_path` | `{PROJECT}` 的绝对路径（本机实际路径） |

**日志目录（全局，固定）**：`~/_sxg/llm_session_log/`

不存在则创建。归档按机器独立（`~` 各自解析），本 skill 只写本机归档。
各项目下的 `_sxg/session_log/` 已废弃，勿再写入。

## 2. 收集事实（先读再写，不要编造）

从**当前对话**提取：

- 用户原始目标 / 问题演变
- 实际完成的工作（含文件路径、行为变化）
- 关键决策、踩坑、未竟事项
- 用户明确说「以后再做」的内容

若 `{PROJECT}` 是 git 仓库，运行：

```bash
git -C "{PROJECT}" log --oneline -15
git -C "{PROJECT}" status -sb
```

把**本 session 相关**的 commit 写进摘要（hash + 一行说明）。无关的旧 commit 不要堆。

## 3. 时间与 upsert 解析（必须先跑脚本）

**禁止**用执行 `/session-log` 的当前时刻填时间。用户可能隔几小时或几天才来整理归档。

### 3.1 时间 — `session_times.py`

```bash
# Claude Code；Cursor 将 ~/.claude 替换为 ~/.cursor
python3 ~/.claude/skills/session-log/scripts/session_times.py \
  --transcript "{当前 session transcript 的绝对路径}"
```

transcript 路径（按优先级）：

1. system 注入的当前 transcript 绝对路径
2. `--uuid {uuid}` 自动查找 Cursor `agent-transcripts/` 或 Claude `~/.claude/projects/**/*.jsonl`

保留输出 JSON（含 `session_id`、`date`、`time`、`filename_ts`、`started_at`、
`last_active_at`、`logged_at`）。

| 字段 | 用途 |
|------|------|
| `session_id` | frontmatter + resolve |
| `date` | frontmatter `date`、index「日期」列（**session 开始日**；update 不变） |
| `time` | frontmatter `time`（**最后活跃**；update 刷新） |
| `last_active_at` / `logged_at` | frontmatter |
| `filename_ts` | 仅 **create** 时用于文件名前缀 |
| `fallback: true` | 找不到 transcript；允许用当前时间并在回复说明 |

### 3.2 命名（先定 slug，再 resolve）

| 字段 | 要求 | 示例 |
|------|------|------|
| `session_title` | 5–12 字概括本次工作 | `consistency gate 修复` |
| `suggested_chat_title` | 供 chat 标题；建议带开始日前缀 | `260629 consistency+mlflow-slug` |
| `slug` | 全小写 snake_case、ASCII、≤40 字符 | `consistency_gate_mlflow_slug` |

`suggested_chat_title` 日期前缀用 **session 开始日**（`date` 的 `YYMMDD`）。

### 3.3 Upsert — `session_resolve.py`

```bash
# Claude Code；Cursor 将 ~/.claude 替换为 ~/.cursor
python3 ~/.claude/skills/session-log/scripts/session_resolve.py \
  --uuid "{session_id}" \
  --times-inline '{session_times JSON 单行}' \
  --project "{project}" \
  --slug "{slug}"
```

| 输出 | 含义 |
|------|------|
| `mode: create` | 本 chat 首次归档 |
| `mode: update` | 已有归档，**覆写同一文件** |
| `target_file` / `target_path` | 写入路径（update 时文件名**不变**） |
| `index_action: insert_row` | index 表头下插入新行 |
| `index_action: replace_row` | **替换**含 `({target_file})` 的那一行 |
| `index_line_match` | replace 时用于 StrReplace 的整行原文 |

`session_times.py` 会按 transcript 自动区分 Cursor / Claude；`session_resolve.py` 的 UUID upsert
逻辑两端共用。若 `fallback: true`，才允许人工核对并填写时间。

## 4. 写文件

**路径**：以 resolve 的 `target_path` 为准（不要自行拼新文件名）。

**create**：按 `references/template.md` 新建；frontmatter 必须含 `session_id`。

**update**：

1. Read 现有 md
2. 保留 `session_id`、`date`（开始日不变）
3. 更新 `time`、`last_active_at`、`logged_at`、`summary`、正文各节
4. **禁止** rename 文件

## 5. 更新 index

| `index_action` | 操作 |
|----------------|------|
| `insert_row` | 在 `index.md` 表头下**第一行**插入 |
| `replace_row` | 用 `index_line_match` 整行 **StrReplace**，**禁止**再插一行 |

行格式：

```markdown
| {date} | {project} | [{session_title}]({target_file}) | {一行 summary} | `{suggested_chat_title}` |
```

index「日期」= session **开始日**。

## 6. 登记映射

写入成功后运行：

```bash
# Claude Code；Cursor 将 ~/.claude 替换为 ~/.cursor
python3 ~/.claude/skills/session-log/scripts/session_resolve.py \
  --register --uuid "{session_id}" --file "{target_file}" \
  --started-at "{started_at}"
```

维护 `~/_sxg/llm_session_log/.session_map.json`（勿手改）。

## 7. 回复用户

用简短中文告知：

1. **新建**或**更新同一条**，以及路径
2. `date` / `time` 来源；若 `fallback` 则说明
3. 检索：`~/_sxg/llm_session_log/index.md`；不够时 agent 用 `session-search`
4. `suggested_chat_title`：Cursor / Claude Code 都在回复**最后一行**单独输出
   `/rename {suggested_chat_title}`。若已安装 Stop hook `auto_rename_on_stop.py`，会经 tmux
   `send-keys` 自动执行；未安装时用户仍可手动运行该命令。

不要继续写无关代码，除非用户接着提新任务。

## 8. 与 handoff / 项目 changelog 的边界

| 工具 | 用途 |
|------|------|
| **session-log**（本 skill） | 归档「这次 chat 做了什么」，方便人类回顾、找 session |
| **handoff** | 给**下一个 agent** 接手的待办与上下文 |
| **项目 changelog** | 产品/代码变更史（另议，不在本 skill 范围） |

若用户既要关 session 又要交接，先完成 session-log，再询问是否另跑 `/handoff`。

## 9. 存量回填（一次性）

脚本 `scripts/session_backfill.py`：从 Cursor transcript 写入记录反查 uuid，注入
`session_id` 并生成 `.session_map.json`。

```bash
python3 ~/.cursor/skills/session-log/scripts/session_backfill.py          # 预览
python3 ~/.cursor/skills/session-log/scripts/session_backfill.py --apply  # 写入
```

同一 chat 重复归档会先合并（见脚本内 `MERGE_GROUPS`），再回填。

**仅 Cursor 测试**；Claude Code 未验证。
