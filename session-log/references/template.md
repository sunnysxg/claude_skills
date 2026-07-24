# Session Log 模板

写入 `~/_sxg/llm_session_log/{target_file}.md` 时使用（create 时 `{target_file}` 由
`session_resolve.py` 给出；update 时沿用已有文件名）。

## 时间字段（Cursor / Claude Code）

| 字段 | 含义 | 来源 |
|------|------|------|
| `date` | session **开始**日期 | `session_times.py` 自动识别 Cursor / Claude → `date`；**update 时不变** |
| `time` | **最后一条实质用户消息**（/session-log 前） | `session_times.py` → `time`；update 时刷新 |
| `filename_ts` | 文件名前缀 12 位（仅 create） | 开始 `YYYYMMDD` + 最后活跃 `HHMM` |

## Upsert（同 chat 多次 log）

1. `session_resolve.py --uuid …` → `mode: create|update`
2. **update**：覆写**同一文件**；index **替换**原行，禁止新增行
3. 文件名首次创建后**冻结**（不因后续 last_active 变化而 rename）
4. 写入后：`session_resolve.py --register --uuid … --file … --started-at …`

## Frontmatter 标准（必须统一）

| 字段 | 类型 | 规则 |
|------|------|------|
| `session_id` | string | 双引号；Cursor/Claude chat UUID；**create/update 均必填** |
| `session_title` | string | 双引号；5–12 字 |
| `date` | date | `YYYY-MM-DD`，不加引号；**session 开始日** |
| `time` | string | 双引号；`"HH:MM"` 24h；**最后活跃** |
| `last_active_at` | string | 双引号；ISO8601；来自 `session_times.py` |
| `logged_at` | string | 双引号；ISO8601；本次写入时刻 |
| `project` | string | 项目根目录名 snake_case 化；不加引号 |
| `project_path` | string | 双引号；项目根绝对路径 |
| `summary` | string | 双引号；一行 |
| `suggested_chat_title` | string | 双引号 |
| `keywords` | list | YAML 列表，小写 tag |
| `git_commits` | list | 本 session 相关 hash；无则 `[]` |

---

```markdown
---
session_id: "00000000-0000-0000-0000-000000000000"
session_title: ""
date: YYYY-MM-DD
time: "HH:MM"
last_active_at: "YYYY-MM-DDTHH:MM:SS+08:00"
logged_at: "YYYY-MM-DDTHH:MM:SS+08:00"
project: project_dir_name
project_path: "/abs/path/on/this/machine"
summary: ""
suggested_chat_title: ""
keywords: []
git_commits: []
---

# Session: {session_title}

> **Chat 标题建议**：`{suggested_chat_title}`

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

## index.md 表头（新建时用）

路径：`~/_sxg/llm_session_log/index.md`

```markdown
# Session Log Index

全局 LLM session 归档（本机），目录：`~/_sxg/llm_session_log/`。关 session 前用
`/session-log` 追加；同一 chat 再次 log 时**更新**已有行，不新增。

文件名以 12 位时间戳开头（开始日期 + 最后活跃时分）；index「日期」列是 session 开始日。
同一 chat 的 `session_id` 映射见 `.session_map.json`。

| 日期 | 项目 | Session | 摘要 | Chat 标题建议 |
|------|------|---------|------|---------------|
```

- **create**：新条目插入表头**下方第一行**（最新在上）
- **update**：找到链接到 `{target_file}` 的行，**整行替换**
