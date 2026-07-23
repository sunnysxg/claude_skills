# Agent 工作约定

- 本仓库是公开、可移植的 skills 单一事实源。禁止提交 auth、token、SSH 私钥、整份
  `~/.codex/config.toml`、Computer Use allowlist、Clash 本机配置或其他凭据。
- 安装集合只由 `skills.manifest.json` 声明；不要恢复根目录 Git symlink，也不要通过扫描所有
  目录自动安装未声明内容。
- Windows 同步器必须保持 `-DryRun`、`Doctor`、幂等、错误链接显式修复，以及普通文件/
  真实目录绝不覆盖。测试只使用隔离临时根，不直接拿 live 客户端目录做破坏性验证。
- Linux 同步器必须读取同一 manifest，保持 `--dry-run`、`doctor`、幂等和显式
  `--repair-links`；只支持 Linux，不为未验收的 macOS 暗示兼容性。
- `sync.local.json` 是 machine-local override，保持 untracked。公共规则与机器私有内容分层，
  不整文件同步用户级配置。
- 修改 skill 时完整读取其 `SKILL.md` 和本次涉及的 references/scripts；同步更新 README 与相关
  设计文档，避免平台路径和兼容性说明漂移。
- 并行 agent 使用不同 worktree/branch，通过 Git 协调；禁止两个 agent 同时写同一 checkout。
- Git 提交与推送遵循 `global/GIT.md`；只有用户明确要求时才 commit/push。
