# claude_skills

我自己日常使用的 Claude Code skills，实现诸如"在 playground 新建项目帮我尝试..."、"当前 session 到上限，汇总工作为交接文档给下一个 agent"等短指令。

## Skills

| Skill | Description |
|-------|-------------|
| `handoff` | Write a handoff doc for the next session/agent |
| `pickup` | Pick up from a previous session's HANDOFF.md |
| `lq` | Log a Q&A to the project's `_sxg/问答记录.md` |
| `playground` | Create a new experiment folder under `playground/` |
| `neat-freak` | End-of-session knowledge cleanup — reconcile docs and memory against code |

## Credits

`neat-freak` is originally authored by [kkkkhazix](https://github.com/kkkkhazix/khazix-skills), used here under the MIT License.
