# 全局规则（跨项目通用）

- 全局归档根：`~/_sxg/`（每台机器各一份，不跨机共享）
  - `~/_sxg/llm_session_log/` — session 摘要归档，索引在 `index.md`
  - `~/_sxg/handoff/{project}.md` — 项目交接文档（个别老项目仍用项目根 `HANDOFF.md`）
- agent 写文件时遵循 `~/.claude/skills/conventions.md`：
  全小写 snake_case、纯 ASCII 路径（中文进内容不进路径）、时间戳 12 位 `YYYYMMDDHHMM`、
  跨项目路径用 `~` 开头不用绝对路径。
- 关 session 前用户可能用 `/session-log` 归档本次工作；要找历史 session 用 `/session-search`；
  交接与接手用 `/handoff`、`/pickup`。
