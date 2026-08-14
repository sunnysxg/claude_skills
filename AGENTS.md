# Agent 工作约定

- 本仓库是公开、可移植的 skills 单一事实源。禁止提交 auth、token、SSH 私钥、整份
  `~/.codex/config.toml`、Computer Use allowlist、Clash 本机配置或其他凭据。
- 安装集合只由 `skills.manifest.json` 声明；每个 skill/alias 必须显式声明 `platforms`，
  alias 必须声明 `canonical`。不要恢复根目录 Git symlink，也不要通过扫描所有目录自动安装
  未声明内容。Codex 用户 skill 只允许安装到 `~/.agents/skills`；`~/.codex/skills/.system`
  是 Codex 自带内容，不得声明为客户端目标或由同步器接管。
- 跨客户端全局正文只维护 `global/COMMON.md`。`managed_rules` 只生成声明的 Cursor 用户规则
  文件和 Codex `AGENTS.md` 标记区块；不得覆盖 Codex 块外机器私有内容，也不得接管整个
  `~/.cursor/rules`。畸形/重复标记和未受管的同名 Cursor 文件必须报冲突。
- Windows 同步器必须保持 `-DryRun`、`Doctor`、幂等、错误链接显式修复，以及普通文件/
  真实目录绝不覆盖；规则同步还必须保持 `Scope=Skills/Rules/All`、原子写入和块外内容
  保留。测试只使用隔离临时根，不直接拿 live 客户端目录做破坏性验证。
- Linux 同步器必须读取同一 manifest，保持 `--dry-run`、`doctor`、幂等和显式
  `--repair-links`，并与 Windows 保持相同的 `--scope` 与 managed-rule 安全语义；只支持
  Linux，不为未验收的 macOS 暗示兼容性。
- `sync.local.json` 是 machine-local override，保持 untracked。公共规则与机器私有内容分层，
  可逐客户端、逐 canonical skill 启停；不整文件同步用户级配置，也不因禁用自动删除链接。
- 修改 skill 时完整读取其 `SKILL.md` 和本次涉及的 references/scripts；同步更新 README 与相关
  设计文档，避免平台路径和兼容性说明漂移。
- 跨平台 skill 的公共 `SKILL.md` 只做平台路由；平台差异放直接引用的
  `references/windows.md`、`references/linux.md` 与对应脚本。优先运行时探测，机器路径只用
  本机环境变量覆盖，不硬编码 hostname、浏览器或字体位置。
- 并行 agent 使用不同 worktree/branch，通过 Git 协调；禁止两个 agent 同时写同一 checkout。
- Git 操作遵循 `git-workflow/references/git.md`；本仓库规则：
  - session 开始：本仓库多机共用，动手前先 `git fetch` 对比远端；落后且可 fast-forward
    时直接 pull，有分叉或工作区不干净时报告后再定
  - commit：用户明确要求时执行，一次要求覆盖本轮连续、相关的改动
  - push：仅在用户明确要求时执行
  - branch / pull_request：沿用现有流程，需要新建时询问
  - commit_message：`[模块][Tag] 中文摘要` 模板，模块名见 `conventions.md` 第 11 节
