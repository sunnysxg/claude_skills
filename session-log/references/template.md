# Session Log 模板

写入 `/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/[{project}]{YYMMDDHHMM}_{slug}.md` 时使用。

## Frontmatter 标准（必须统一）

| 字段 | 类型 | 规则 |
|------|------|------|
| `session_title` | string | 双引号；5–12 字 |
| `date` | date | `YYYY-MM-DD`，不加引号 |
| `time` | string | 双引号；`"HH:MM"` 24h |
| `project` | string | 项目根目录名；不加引号（纯字母数字下划线） |
| `project_path` | string | 双引号；项目根绝对路径 |
| `summary` | string | 双引号；一行 |
| `suggested_chat_title` | string | 双引号 |
| `keywords` | list | YAML 列表，小写 tag |
| `git_commits` | list | 本 session 相关 hash；无则 `[]` |

---

```markdown
---
session_title: ""
date: YYYY-MM-DD
time: "HH:MM"
project: ProjectDirName
project_path: "/cpfs01/nfshome/xgsun/..."
summary: ""
suggested_chat_title: ""
keywords: []
git_commits: []
---

# Session: {session_title}

> **Cursor 标题**：发送 **`/rename {suggested_chat_title}`**（或侧边栏 Rename）

## 目标

（用户最初想解决什么）

## 完成事项

- （可执行、带路径/命令/行为变化）

## 关键决策与坑

- （为什么这样选；踩过什么坑）

## Git（本 session）

| Commit | 说明 |
|--------|------|
| `abc1234` | … |

## 未竟 / 下次继续

- [ ] …

## 相关路径

- `path/to/file`
- `_sxg/TODO.md`
```

---

## INDEX.md 表头（新建时用）

路径：`/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/INDEX.md`

```markdown
# Session Log Index

全局 LLM session 归档，目录：`/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/`。关 session 前用 `/session-log` 追加。

按文件名排序即按「项目 → 时间」倒序（同项目内较新的在前）。

| 日期 | 项目 | Session | 摘要 | Chat 标题建议 |
|------|------|---------|------|---------------|
```

新条目插入表头**下方第一行**（最新在上）。
