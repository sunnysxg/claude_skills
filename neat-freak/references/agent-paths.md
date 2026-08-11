# Agent 规则、记忆与 skill 路径速查

不同 Agent 平台的规则、记忆与 skill 入口不同。平台机制会变；涉及写入、加载顺序或尺寸上限
时，优先核对当前官方文档和本机诊断，不把本表当成永远不变的事实。

通用原则：

- 区分人工维护的规则、Agent 自动记忆、机器生成的历史/索引；三者不能共用写入规则。
- 发现多个平台目录不等于每个平台都在使用；先检查 realpath、加载列表和当前客户端。
- 同名 skill 的复制副本不会自动合并。只编辑权威真身；复制安装要显式同步或退役。

## Claude Code

| 用途 | 路径 |
|---|---|
| 跨会话记忆(全局) | `~/.claude/projects/<encoded-project-path>/memory/` |
| 记忆索引文件 | `~/.claude/projects/<...>/memory/MEMORY.md` |
| 全局指令 | `~/.claude/CLAUDE.md` |
| 项目级指令 | 项目根 `CLAUDE.md`(可层级嵌套) |
| Skills 目录 | `~/.claude/skills/<name>/SKILL.md` |

记忆文件用 YAML frontmatter:`name`、`description`、`type`(user / feedback / project / reference)。

## Cursor

| 用途 | 路径 |
|---|---|
| 项目级指令 | 项目根 `AGENTS.md`（或 `CLAUDE.md`，Cursor 会兼容读取） |
| 项目规则目录 | `<project>/.cursor/rules/*.mdc`（旧式 `.cursorrules` 已弃用） |
| 用户级全局规则 | 官方入口为 Cursor Settings → Rules → User Rules；支持 user file rules 的版本也读取 `~/.cursor/rules/*.mdc` |
| 斜杠命令 | `.cursor/commands/<name>.md` |
| **Skills 目录** | `~/.cursor/skills/<name>/SKILL.md`（**不**自动读 `~/.claude/skills/`） |

Cursor 没有独立的「记忆文件 + 索引」机制（内置 Memories 由 IDE 自己管理，不在文件层）。
同步时参照 Codex 的做法：跨会话项目事实写进项目根 markdown。

**与 `~/.claude/skills` 同步**：单一事实源在 claude_skills 仓库；Windows 用 junction，
Linux 用 symlink：

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ~/.claude/skills/scripts/sync_skills.ps1 -Command Sync -DryRun            # Windows
bash ~/.claude/skills/scripts/sync_skills.sh sync --dry-run                # Linux
```

`~/.cursor/skills/` 里已是真实目录的 skill（如 `factorhub-handadd`）保留不动。

## OpenAI Codex

| 用途 | 路径 |
|---|---|
| Codex home | `$CODEX_HOME`，默认 `~/.codex` |
| 跨会话指令(全局) | `$CODEX_HOME/AGENTS.override.md`；不存在时读 `$CODEX_HOME/AGENTS.md` |
| 项目级指令 | 项目根 `AGENTS.md`(可层级嵌套) |
| 项目级 override | `AGENTS.override.md`(若存在,覆盖同目录 AGENTS.md) |
| Skills 目录 | `~/.agents/skills/<name>/SKILL.md` 或项目内 `.agents/skills/<name>/` |
| System skills | 由 Codex 自带；本机可见于 `~/.codex/skills/.system`，不是用户安装目标 |

截至 2026-08-11，Codex 官方用户级和项目级 skill 根分别是 `~/.agents/skills` 与
`.agents/skills`。这不是把整个 `~/.codex` 改名为 `~/.agents`：配置、全局指令、session 和
系统内容仍属于 `$CODEX_HOME`。`~/.codex/skills/<用户 skill>` 是历史/第三方 legacy 安装位置；
部分 Codex 版本可能为向后兼容继续扫描，但文件存在本身不能证明当前客户端正在消费，必须看
实际加载诊断或显式配置。新用户 skill 不应再装到这里；不要删除 `~/.codex/skills` 根或 `.system`。

路径历史容易误导：

- OpenAI 于 2026-02-01 在 [openai/codex#10317](https://github.com/openai/codex/pull/10317)
  加入项目级 `.agents/skills`。PR 直接说明动机：不同 Agent 各用自己的目录会迫使用户做
  symlink/复制，统一到 `.agents/` 更容易共享；旧 `.codex/skills` 将被弃用。
- 2026-02-03 的 [openai/codex#10437](https://github.com/openai/codex/pull/10437) 加入用户级
  `~/.agents/skills`，并明确当时只是暂时保留 `~/.codex/skills` 向后兼容，`.system` 位置不变。
- 原作者随后在 2026-04-29 的提交 `83fc7bd` 中，按当时实机仍可加载的现象把 reference 改回
  `.codex/skills`。结合上面的兼容设计，这只能证明 legacy loader 当时仍工作，不能证明旧根
  重新成为推荐路径。

截至 2026-08-11，当前官方文档使用 `.agents/skills`。维护时应以当前官方文档和本机加载
列表为准，而不是照抄旧版本 reference。

Codex 可能提供宿主生成的 memories、rollout summaries 或索引。这些内容没有明确写入授权时
只读；项目稳定事实仍写入作用域正确的 `AGENTS.md` / docs，不直接编辑机器生成记忆。

Codex 默认只查 `AGENTS.md` / `AGENTS.override.md`；只有本机 `config.toml` 的
`project_doc_fallback_filenames` 显式列出其他名字时，才把 `TEAM_GUIDE.md`、`.agents.md` 等
当作 fallback（默认列表为空）。`project_doc_max_bytes` 控制整个项目指令链的合计读取上限，维护时
应读取本机配置，不把某个版本的默认值写死为项目约束。

## OpenClaw

| 用途 | 路径 |
|---|---|
| 用户级 skills | `~/.openclaw/skills/<name>/SKILL.md`（首次运行自动创建） |
| 项目级 skills | `.openclaw/skills/<name>/SKILL.md`（仓库根目录下） |
| Workspace skills | 当前 workspace 的 `skills/` 目录 |

**加载优先级**：workspace > project-agent > personal-agent > managed/local > bundled > extra dirs。同名 skill 高优先级覆盖低优先级。

OpenClaw 没有独立的"记忆文件 + 索引"机制，跨会话信息可放在项目根的 markdown（CLAUDE.md / AGENTS.md / 等价文件）里，参照 Codex 的做法。frontmatter 支持 `metadata.openclaw` 字段做加载时的 gating（按 OS、环境变量、二进制依赖筛选），但不是 neat-freak 必需的。

## OpenCode

| 用途 | 路径 |
|---|---|
| 全局配置 | `~/.config/opencode/` |
| 项目配置 | `.opencode/` |
| Skills 目录(项目) | `.opencode/skills/`、`.claude/skills/`、`.agents/skills/` 等兼容目录 |
| Skills 目录(全局) | `~/.config/opencode/skills/`、`~/.claude/skills/`、`~/.agents/skills/` |

OpenCode 读取 Claude Code 和 Codex 的兼容目录，所以同一个 skill 装在 `~/.claude/skills/`
下即可识别。OpenClaw 走自己的 `~/.openclaw/skills/`，需要单独装一份（或用符号链接）。

## 如果当前 agent 没有独立记忆系统

跳过"记忆"那一层,把功夫全花在:
- 项目根 markdown(CLAUDE.md / AGENTS.md / 本平台等价文件)
- README.md
- docs/

仍然是有效的同步——记忆是锦上添花,docs 才是项目知识的最低保障。

## 共存检查

1. 列出实际存在的平台目录和同名 skill 的 realpath。
2. 判断每个入口是 junction/symlink、复制安装还是独立真实目录。
3. 只修改权威真身；复制副本若没有独有内容，应退出扫描路径，而不是再链接一份制造重复。
4. 验证客户端实际加载，而不只验证文件存在；使用 skill list、诊断入口或新 task。
5. Windows/Linux 的链接方式服从本仓库 manifest 和同步器，不手工链接整个 skills 根。

## 跨平台共存策略

如果一个项目同时被 Claude Code 用户和 Codex 用户使用,推荐:

- **项目根同时放 `CLAUDE.md` 和 `AGENTS.md`**,内容可以互相 symlink 或在两边维护
- 或者一份内容主文件 + 另一份用一行 `See CLAUDE.md` 跳转
- docs/ 和 README 是平台中立的,不需要分两份

## 官方复核入口

- Codex skills：<https://learn.chatgpt.com/docs/build-skills>
- Codex AGENTS.md：<https://learn.chatgpt.com/docs/agent-configuration/agents-md>
- Agent Skills specification：<https://agentskills.io/specification>
