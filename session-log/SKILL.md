---
name: session-log
description: >
  关闭 session 前，把本次对话的工作摘要归档到 ~/_sxg/llm_session_log/ 并更新索引，
  同时给出建议的 chat 标题。
disable-model-invocation: true
---

# Session Log — 关 session 前写摘要

用户要在**结束本次 chat 之前**留下可检索记录，避免「几天前改过什么但找不到对应 session」。
chat 侧边栏只能按标题/时间浏览，这个归档 + 索引是**刻意为之的可搜索层**；检索用
`session-search`，本 skill 只负责写入。

你的任务：**回顾当前对话**，写一份结构化 session 摘要到**全局归档目录**，并生成
`suggested_chat_title`。

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

## 3. 命名

生成两个名字（简体中文或短英文均可，但要**可搜索**）：

| 字段 | 要求 | 示例 |
|------|------|------|
| `session_title` | 5–12 字概括本次工作 | `consistency gate 修复` |
| `suggested_chat_title` | 供 chat 标题与侧边栏检索；建议带日期前缀 | `260629 consistency+mlflow-slug` |

`slug`（文件名用）：全小写 snake_case、纯 ASCII、≤40 字符，从 `session_title` 派生，
如 `consistency_gate_mlflow_slug`。中文只进标题字段和正文，不进文件名。

**文件名**：`{YYYYMMDDHHMM}_{project}_{slug}.md`

- `{YYYYMMDDHHMM}`：关 log 时的本地时间，12 位，24h，无分隔符（如 `202606291743`）
- 示例：`202606291743_hzy_projects_hcp_mlflow_login.md`

## 4. 写文件

**路径**：`~/_sxg/llm_session_log/{YYYYMMDDHHMM}_{project}_{slug}.md`

**正文格式** — 严格按 `references/template.md`（YAML frontmatter + 章节）。写完后读取
template 核对一遍。

**索引**：在 `~/_sxg/llm_session_log/index.md` **表头下方第一行**插入新行（文件不存在则按
template 建表头）：

```markdown
| {YYYY-MM-DD} | {project} | [{session_title}]({filename}.md) | {一行 summary} | `{suggested_chat_title}` |
```

## 5. 回复用户

用简短中文告知：

1. 写入路径
2. 以后如何检索：看 `~/_sxg/llm_session_log/index.md`；提到「上次/最近 session」且项目文档
   不够时 agent 会自动查 `session-search`
3. 给出 `suggested_chat_title`，按平台处理：
   - **Cursor**：回复**最后一行**单独给出可直接复制发送的 `/rename {suggested_chat_title}`
     （若用户已设过不同标题则跳过并说明）
   - **Claude Code**：没有 /rename 命令，标题在侧边栏 UI 手动改；只给出建议标题即可

不要继续写无关代码，除非用户接着提新任务。

## 6. 与 handoff / 项目 changelog 的边界

| 工具 | 用途 |
|------|------|
| **session-log**（本 skill） | 归档「这次 chat 做了什么」，方便人类回顾、找 session |
| **handoff** | 给**下一个 agent** 接手的待办与上下文 |
| **项目 changelog** | 产品/代码变更史（另议，不在本 skill 范围） |

若用户既要关 session 又要交接，先完成 session-log，再询问是否另跑 `/handoff`。
