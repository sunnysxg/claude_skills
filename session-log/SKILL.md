---
name: session-log
description: >
  在关闭 session 前，生成本次对话的工作摘要并写入全局 _sxg/LLM_session_log/。
  仅当用户显式调用时启用："/session-log"、"/closelog"、"/关session"、
  "写 session log"、"session 结束总结"、"关 session 前总结"。
  不要自动触发；不要在普通写代码/改文档任务中主动调用。
disable-model-invocation: true
---

# Session Log — 关 session 前写摘要

用户要在**结束本次 chat 之前**留下可检索记录，避免「几天前改过什么但找不到对应 session」。

你的任务：**回顾当前对话**，写一份结构化 session 摘要到**全局归档目录**，并生成 `suggested_chat_title`；回复**末尾**给出可直接发送的 `/rename` 命令。

## 1. 确定项目

按优先级：

1. 用户 `@` 的路径所在项目（含 `CLAUDE.md` 的子目录根）
2. 从 cwd 向上找最近的 `CLAUDE.md` 或 git 根
3. 多项目并列时，以**主要改动最多的那个**为准；不确定则问用户

记为 `{PROJECT}`（绝对路径）。元信息字段：

| 字段 | 取值 |
|------|------|
| `project` | 项目根目录名（如 `HzyProjects`、`FactorInfra`、`260507_paper_skill_extractor`） |
| `project_path` | `{PROJECT}` 的绝对路径 |

**日志目录（固定，不在各项目下）**：

`/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/`

不存在则创建。各项目 `_sxg/session_log/` 已废弃，勿再写入。

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

生成两个名字（简体中文或短英文 slug 均可，但要**可搜索**）：

| 字段 | 要求 | 示例 |
|------|------|------|
| `session_title` | 5–12 字概括本次工作 | `consistency gate 修复` |
| `suggested_chat_title` | 供 `/rename` 与侧边栏标题；建议带日期前缀 | `260629 consistency+mlflow-slug` |

`slug`（文件名用）：小写、连字符，从 `session_title` 派生，≤40 字符，如 `consistency-gate-mlflow-slug`。中文 slug 也可，保持可搜索即可。

**文件名**（含项目前缀，便于排序与过滤）：

`[{project}]{YYMMDDHHMM}_{slug}.md`

- `{YYMMDDHHMM}`：关 log 时的本地时间，24h，无分隔符（如 `2606291743`）
- 示例：`[HzyProjects]2606291743_hcp-mlflow-login验证.md`

## 4. 写文件

**路径**：`/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/[{project}]{YYMMDDHHMM}_{slug}.md`

**正文格式** — 严格按 `references/template.md`（YAML frontmatter + 章节）。写完后读取 template 核对一遍。

**索引**：在 `/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/INDEX.md` **表头下方第一行**插入新行（文件不存在则按 template 建表头）：

```markdown
| {YYYY-MM-DD} | {project} | [{session_title}]({filename}.md) | {一行 summary} | `{suggested_chat_title}` |
```

## 5. 回复用户

用简短中文告知：

1. 写入路径
2. 以后如何检索：看 `/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/INDEX.md`；提到「上次/最近 session」且文档不够时 agent 会自动查 `session-search`

**回复最后一行必须是**（单独一行、可直接复制发送；若用户已用 `/rename` 设过标题且与建议不同，则跳过此步并说明已保留现标题）：

```
/rename {suggested_chat_title}
```

Agent 无官方 rename 工具；用户发送上述 slash 命令即可改 chat 标题（或侧边栏右键 Rename）。

不要继续写无关代码，除非用户接着提新任务。

## 6. 与 handoff / 项目 changelog 的边界

| 工具 | 用途 |
|------|------|
| **session-log**（本 skill） | 归档「这次 chat 做了什么」，方便人类回顾、找 session |
| **handoff** | 给**下一个 agent** 接手的待办与上下文 |
| **项目 changelog** | 产品/代码变更史（另议，不在本 skill 范围） |

若用户既要关 session 又要交接，先完成 session-log，再询问是否另跑 `/handoff`。

## 7. Cursor 原生检索 vs 本归档

Cursor **没有**跨项目、按关键词检索历史 session 摘要的能力。侧边栏 chat 历史只能按标题/时间浏览当前工作区；`agent-transcripts/*.jsonl` 是原始对话流，不适合人类检索。

本目录 + `INDEX.md` 是**刻意为之的可搜索归档**。检索用 **`session-search`** skill（显式 `/session-search`，或用户指向上次/最近 agent 工作且项目文档不够时自动查）；本 skill 只负责写入。

## 8. 以后可选：Hook

Cursor 支持 `sessionEnd` hook，但**自动生成摘要仍需 LLM**，hook alone 不够。可靠做法仍是用户关 tab 前手动 `/session-log`。若用户以后要 hook 提醒，见 Cursor `create-hook` skill（例如 sessionEnd 弹提醒「记得 /session-log」）。
