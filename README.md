# claude_skills

我自己日常使用的 agent skills（Claude Code / Cursor / Codex / OpenCode 等平台通用），实现诸如「在 playground
新建项目帮我尝试…」「当前 session 到上限，汇总工作为交接文档给下一个 agent」等短指令。

命名与路径规范见 **[conventions.md](conventions.md)**：所有跨项目路径一律 `~` 开头，
两台 Windows + Linux 集群共用同一份 skill；全局归档在 `~/_sxg/`（每台机器各一份）。
仓库内 agent 的安全与并行约定见 [AGENTS.md](AGENTS.md)。

## Skills

| Skill | 说明 |
|-------|------|
| `git-workflow` | 执行 Git 写操作；首次解析项目规范并记录到 `_sxg/project_config.md`，后续直接复用 |
| `handoff` | 写交接文档到 `~/_sxg/handoff/{project}.md`，供下一个 session/agent 接手 |
| `pickup` | 读取交接文档并继续（兼容旧式项目根 `HANDOFF.md`） |
| `lq` | 把当前问答记录到项目的 `_sxg/qa_log.md` |
| `playground` | 在 `playground/` 下新建实验项目 |
| `neat-freak` | 会话收尾时整理文档与记忆，与代码对齐 |
| `mmd-explain` | 用 Mermaid 图示解释（`.mmd` + PNG，默认输出到项目 `_sxg/diagram/`）；Windows/Linux 分别使用 PowerShell/Bash renderer |
| `session-log` | 在 Cursor / Claude Code 归档并 upsert 同一 chat；可选 Stop hook 经 tmux 自动执行标题建议 |
| `session-search` | 按关键词、项目、时间检索已归档的 session 摘要 |

## 部署

- 仓库 clone 到 `~/.claude/skills`（Claude Code 直接读取，OpenCode 也扫描该目录）。
- 安装集合由 [skills.manifest.json](skills.manifest.json) 声明，包括每个 skill 的目标客户端与
  支持平台；同步器不再扫描所有目录猜测 skill。
- 每台机器复制 `sync.local.example.json` 为 `sync.local.json` 后，先把 `machine_id` 改成稳定
  机器名；没有安装的客户端在 `clients` 中设为 `enabled: false`，某台机器不需要的 skill 在
  `skills.<name>.enabled` 中关闭。关闭只停止管理该入口，不自动删除已有链接。
- Windows 上先预览，再同步 Cursor 与 Codex：

  ```powershell
  Copy-Item sync.local.example.json sync.local.json
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 -Command Sync -DryRun
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 -Command Sync
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 -Command Doctor
  ```

  默认 `Scope=All`，同时同步 skill 链接和全局规则投影；可用
  `-Scope Skills` / `-Scope Rules` 单独处理。Cursor skill 目标为 `~/.cursor/skills`；
  Codex 官方用户级 skill 目标为 `~/.agents/skills`。脚本逐 skill 创建目录联接，不覆盖
  已有真实目录。`~/.codex/skills` 是默认关闭的存量兼容目标，且永不接管 `.system`。
  `session-log` 暂不安装给 Codex：它仍使用 Claude/Cursor 专属的显式调用 frontmatter，
  且需要补齐 Codex session upsert。
- Linux 上同样先预览，再同步 Cursor 与 Codex：

  ```bash
  cp sync.local.example.json sync.local.json
  bash scripts/sync_skills.sh sync --dry-run
  bash scripts/sync_skills.sh sync
  bash scripts/sync_skills.sh doctor
  ```

  该脚本需要 Bash、`jq` 和 GNU `realpath`，默认同时同步 skill 链接和全局规则；可用
  `--scope skills` / `--scope rules` 单独处理。它按 manifest 为每个 skill 创建符号链接；
  `~/.cursor/skills/` 和 `~/.agents/skills/` 下已有的真实目录视为客户端专属内容，不会被
  覆盖或删除。旧命令 `scripts/sync_cursor_skills.sh` 仍保留，作为只处理 Cursor 的兼容入口。
  当前只承诺 Windows 与 Linux，不宣称支持 macOS。
- 跨平台 skill 的 `SKILL.md` 只保留公共流程和平台路由；运行时仅加载当前平台 reference。
  `mmd-explain` 在 Windows 使用
  [`references/windows.md`](mmd-explain/references/windows.md)，在 Linux 使用
  [`references/linux.md`](mmd-explain/references/linux.md)。浏览器、renderer 和字体由各平台
  doctor 自动探测，机器私有路径仅通过本机环境变量覆盖，不写进 Git。
- [global/COMMON.md](global/COMMON.md) 是跨客户端全局规则的唯一维护源。三个客户端用不同
  的薄适配读取同一正文：
  - Claude：`~/.claude/CLAUDE.md` 导入 `skills/global/CLAUDE.md`，后者只含
    `@COMMON.md`；机器特有内容可继续放在用户级文件的导入行下面。
  - Cursor：同步器生成用户级
    `~/.cursor/rules/claude-skills-common.mdc`（`alwaysApply: true`）。这是当前 Cursor
    3.9.16 的文件化 User Rule；同步器只管理这一文件，不接管整个 `rules/` 目录。
  - Codex：同步器只替换 `~/.codex/AGENTS.md` 的
    `<!-- BEGIN/END claude_skills:global-common -->` 标记区块，块外本机规则原样保留。
- 首次接线或 COMMON 更新后，用新 task 验证实际加载；Cursor 如未立即刷新，执行 Reload
  Window 后在 Settings → Rules 确认 `claude-skills-common` 出现在用户规则中。
- 规则投影与 skill 链接分别计数。同步器遇到畸形标记、目录/reparse target，或同名但没有
  管理标记的 Cursor 文件时只报冲突，不覆盖。Windows 隔离回归可运行：

  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_sync_rules.ps1
  ```
- 归档目录 `~/_sxg/` 各机器独立，skill 首次写入时自动创建。

双机 Remote Control、SSH host、Computer Use、machine-local 配置边界和验收矩阵见
[docs/sync-design.md](docs/sync-design.md)。同步仓库不包含 ChatGPT/Codex auth、SSH 私钥、
整份 `~/.codex/config.toml`、Computer Use allowlist 或 Clash 本机运行期配置。

## Credits

`neat-freak` 原作者为 [kkkkhazix](https://github.com/kkkkhazix/khazix-skills)，在此按 MIT License 使用。
