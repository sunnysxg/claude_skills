# claude_skills

我自己日常使用的 agent skills（Claude Code / Cursor 等平台通用），实现诸如「在 playground
新建项目帮我尝试…」「当前 session 到上限，汇总工作为交接文档给下一个 agent」等短指令。

命名与路径规范见 **[conventions.md](conventions.md)**：所有跨项目路径一律 `~` 开头，
两台 Windows + Linux 集群共用同一份 skill；全局归档在 `~/_sxg/`（每台机器各一份）。

## Skills

| Skill | 说明 |
|-------|------|
| `handoff` | 写交接文档到 `~/_sxg/handoff/{project}.md`，供下一个 session/agent 接手 |
| `pickup` | 读取交接文档并继续（兼容旧式项目根 `HANDOFF.md`） |
| `lq` | 把当前问答记录到项目的 `_sxg/qa_log.md` |
| `playground` | 在 `playground/` 下新建实验项目 |
| `neat-freak` | 会话收尾时整理文档与记忆，与代码对齐 |
| `mmd-explain` | 用 Mermaid 图示解释（`.mmd` + PNG，默认输出到项目 `_sxg/diagram/`） |
| `session-log` | 关 chat 前写 session 摘要到 `~/_sxg/llm_session_log/` |
| `session-search` | 按关键词、项目、时间检索已归档的 session 摘要 |

## 部署

- 仓库 clone 到 `~/.claude/skills`（Claude Code 直接读取，OpenCode 也扫描该目录）。
- [global/CLAUDE.md](global/CLAUDE.md) 是跨项目通用规则：Claude Code 部署到
  `~/.claude/CLAUDE.md`；Cursor 读取项目根的 `CLAUDE.md`/`AGENTS.md`，通用内容同样来自这份。
- 归档目录 `~/_sxg/` 各机器独立，skill 首次写入时自动创建。

## Credits

`neat-freak` 原作者为 [kkkkhazix](https://github.com/kkkkhazix/khazix-skills)，在此按 MIT License 使用。
