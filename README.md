# claude_skills

我自己日常使用的 Claude Code skills，实现诸如「在 playground 新建项目帮我尝试…」「当前 session 到上限，汇总工作为交接文档给下一个 agent」等短指令。

## Skills

| Skill | 说明 |
|-------|------|
| `handoff` | 写交接文档，供下一个 session/agent 接手 |
| `pickup` | 读取上一个 session 留下的 `HANDOFF.md` 并继续 |
| `lq` | 把当前问答记录到项目的 `_sxg/问答记录.md` |
| `playground` | 在 `playground/` 下新建实验项目 |
| `neat-freak` | 会话收尾时整理文档与记忆，与代码对齐 |
| `mmdexplain` | 用 Mermaid 图示解释（`.mmd` + PNG，默认输出到 `_sxg/图示回答/`） |
| `session-log` | 关 chat 前写 session 摘要到全局 `_sxg/LLM_session_log/` |
| `session-search` | 按关键词、项目、时间检索已归档的 session 摘要 |

## Credits

`neat-freak` 原作者为 [kkkkhazix](https://github.com/kkkkhazix/khazix-skills)，在此按 MIT License 使用。
