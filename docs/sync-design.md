# 跨设备、跨客户端同步设计

本文定义两台 Windows 电脑与 Linux host 上的 ChatGPT/Codex、Claude Code、Cursor 与
OpenCode 如何共享公共 skills，同时保留每台机器的认证、网络和 GUI 权限边界。

## 1. 分层

| 层 | 解决的问题 | 是否进本仓库 |
|---|---|---|
| Git 公共层 | skills、manifest、跨平台规则、同步/检查脚本 | 是 |
| machine override | `machine_id`、客户端启用状态、非默认安装根 | 否，使用 `sync.local.json` |
| Remote Control | 支持的客户端与指定 host 配对，进入该 host 的项目和 task | 否，逐设备配对 |
| SSH host | 跨机 filesystem/shell、远端项目、跨 host handoff | 否，使用本机 SSH 配置和密钥 |
| Computer Use | 在实际执行 GUI 的 host 上控制本机应用 | 否，权限与 allowlist 均为 machine-local |
| 运行期/认证 | ChatGPT/Codex auth、SSH 私钥、Clash 本机 DNS/运行期配置 | 否，禁止同步 |

同一 ChatGPT 账号不等于设备自动配对。每个受支持客户端仍需与每个要控制的 host 完成
Remote 设置。远程项目的文件、shell、skills、MCP、浏览器和 Computer Use 都来自实际执行
任务的 host。

SSH 连接只通过 OpenSSH key 和可信 VPN/mesh 使用。不要把 Codex app-server 的 transport
直接暴露到公网或共享网络。跨 host handoff 前，两台机器要保存同一 Git 仓库的匹配项目；
Codex 在目标 host 创建或复用 worktree 并转移 task 和 Git 状态。

Windows Computer Use 使用活动桌面，任务执行期间要保持机器解锁、联网并让目标应用处于
前台。`always_allowed_app_ids` 属于 `$CODEX_HOME/config.toml` 的本机决策，不进入 Git，也
不由同步脚本写入。

## 2. 单一事实源和安装目标

中央仓库固定 clone 到 `~/.claude/skills`：

- Claude Code 与 OpenCode 直接读取该目录。
- Cursor 安装根为 `~/.cursor/skills`。
- Codex 官方用户级 skill 根为 `~/.agents/skills`。
- `~/.codex/skills` 只作为当前存量环境的可选兼容目标，manifest 中名为
  `codex_legacy`，默认关闭；同步时只处理声明的单个 skill，不接管 `.system`。

Windows 使用目录联接（junction），Linux 使用符号链接。不要链接整个客户端 skills 根；
逐 skill 链接才能保留客户端自带或机器专属目录。

`skills.manifest.json` 是安装集合的唯一清单。它显式声明 canonical skill、兼容别名、目标
客户端和平台兼容状态，不通过扫描仓库目录猜测安装内容。旧别名 `mmdexplain` 由 manifest
指向 `mmd-explain`，不再依赖 Git symlink；这样 Windows 未启用 `core.symlinks` 时也不会
checkout 成 11 字节文本文件。

链接建立成功不等于客户端一定能加载。`git-workflow` 与 `session-log` 的
`disable-model-invocation` 是 Claude/Cursor 专属 frontmatter，不符合 Codex 使用的 Agent
Skills 标准；当前 manifest 不把这两个 skill 安装给 Codex。后续用 Codex adapter 的
`agents/openai.yaml` 表达显式调用策略，并为 `session-log` 补齐 Codex upsert 后再启用。

## 3. Windows 使用方法

每台 Windows 机器各自创建不入 Git 的 override：

```powershell
Copy-Item sync.local.example.json sync.local.json
```

把 `machine_id` 改成稳定、易识别且不含凭据的名称，例如 `home-win`、`cloud-win`。未创建
override 时，脚本使用归一化 hostname。

先预览，再同步，再检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 -Command Sync -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 -Command Sync
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 -Command Doctor
```

默认处理 Cursor 和 Codex 官方根。只有确认当前客户端确实依赖旧路径时才显式加入：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync_skills.ps1 `
  -Command Sync -Client cursor,codex,codex_legacy -DryRun
```

安全规则：

- 普通文件和真实目录永不覆盖。
- 正确 junction 重复执行不变。
- 指向错误位置的 junction 默认报冲突；只有显式 `-RepairLinks` 才替换链接本身。
- 不自动删除 manifest 之外的目录，也没有 prune 行为。
- 脚本只写选中客户端的 skill 根，不读取或复制认证、密钥、整份 Codex 配置、Computer Use
  allowlist、Clash 配置或 session 归档。

## 4. Linux 使用方法

Linux 使用与 Windows 相同的 manifest 和 machine-local override：

```bash
cp sync.local.example.json sync.local.json
bash scripts/sync_skills.sh sync --dry-run
bash scripts/sync_skills.sh sync
bash scripts/sync_skills.sh doctor
```

依赖 Bash、`jq` 与 GNU `realpath`。默认处理 Cursor 和 Codex 官方根；可以用
`--client cursor` 等参数缩小范围。安全语义与 Windows 一致：

- 普通文件和真实目录永不覆盖。
- 正确 symlink 重复执行不变。
- 错误 symlink 默认报冲突，只有 `--repair-links` 才替换链接本身。
- 不扫描、删除或接管 manifest 之外的客户端专属目录。

旧 `scripts/sync_cursor_skills.sh` 只是一层兼容包装，内部调用 manifest 同步器。当前只支持并
验收 Linux，不宣称支持 macOS。

## 5. COMMON 与全局指令（下一切片）

后续把真正跨平台的个人规则收敛到 `global/COMMON.md`。安装器只维护目标文件中的标记区块：

- Claude：`~/.claude/CLAUDE.md`
- Codex：`~/.codex/AGENTS.md`

标记区块之外是 machine-local 内容，必须原样保留。不要同步整份 `~/.codex/config.toml`；
Codex 官方建议把个人全局习惯放 `~/.codex/AGENTS.md`，把仓库规则放最近的项目
`AGENTS.md`。

## 6. session-log 跨 host（后续切片）

`session_id`/task ID 是同一 task 跨 host handoff 后的 canonical identity，`machine_id` 只记录
来源和最后写入 host，不能取代 task ID。下一版映射至少要记录：

```json
{
  "version": 2,
  "sessions": {
    "task-uuid": {
      "file": "...md",
      "origin_machine_id": "home-win",
      "last_machine_id": "cloud-win",
      "host_history": ["home-win", "cloud-win"]
    }
  }
}
```

当前归档根 `~/_sxg/llm_session_log` 仍是 machine-local。仅增加 `machine_id` 不能让另一台机器
看到旧文件；要实现真正的跨 host 单文件 upsert，必须再选择一种私有传输层：handoff 时通过
SSH 显式复制、或使用不进入本公共仓库的私有同步目录。确定传输层前，Codex adapter 只能在
目标 host 创建同 task 的本地镜像，并明确记录来源，不能宣称全局去重。

## 7. 并行写入约束

两个 agent 不得同时写同一 checkout。每个并行任务使用独立 worktree 和独立分支，通过 Git
commit/merge 协调。Handoff 可以在 Local、worktree 和匹配的 SSH host 项目间移动 task，但
同一分支不能同时 checkout 在两个 worktree。

## 8. 验收矩阵

| 场景 | 期望 | 本切片 |
|---|---|---|
| 两台 Windows 首次 `-DryRun` | 只报告将创建的 junction，不改磁盘 | 已实现 |
| 两台 Windows 正式 Sync 后 Doctor | 每个声明 skill 指向中央仓库，重复运行幂等 | 已实现 |
| 客户端已有真实目录 | 报冲突并保留原目录 | 已实现 |
| 现有错误 junction | 默认报冲突；`-RepairLinks` 才替换 | 已实现 |
| `mmdexplain` 别名 | 指向 canonical `mmd-explain`，不依赖 Git symlink | 已实现 |
| Codex `.system`/插件缓存 | 不扫描、不删除、不覆盖 | 已实现 |
| 每机不同安装根/客户端组合 | untracked override 可改 root/enabled | 已实现 |
| Linux 首次 dry-run | 报告 Cursor/Codex symlink 计划，不创建目录 | 已实现并在 Linux host 隔离验收 |
| Linux Sync、Doctor、重复 Sync | 建立所有声明入口，Doctor 通过且重复运行幂等 | 已实现并在 Linux host 隔离验收 |
| Linux 冲突与修复 | 保留真实目录；错误 symlink 仅显式 repair | 已实现并在 Linux host 隔离验收 |
| Codex skill 格式 | 只安装 Agent Skills 标准兼容项；两个显式调用 skill 等 adapter | 已实现安装边界；adapter 待办 |
| Remote Control | 每个控制端与每个 host 单独配对；同账号不视为已配对 | 人工验收 |
| SSH host | key + 最小权限账户 + VPN/mesh；无公开 app-server listener | 人工验收 |
| Windows Computer Use | 在执行 host 前台运行，保持解锁；allowlist 不跨机 | 人工验收 |
| Git 敏感边界 | auth、私钥、`config.toml`、allowlist、Clash 运行期文件不入库 | 已设计，需 CI 检查 |
| COMMON managed block | 更新公共区块且保留机器私有区块 | 下一切片 |
| 同 task 跨 host session upsert | task ID 不变，记录 host history，私有传输后更新同一文件 | 需先定传输层 |
| 两个 agent 并行 | 独立 worktree/branch，不共写 checkout | 流程约束 |

## 9. 官方参考

- [Codex skills：保存位置、symlink 与渐进加载](https://learn.chatgpt.com/docs/build-skills)
- [Agent Skills 规范：SKILL.md frontmatter](https://agentskills.io/specification)
- [Codex Remote Control、SSH host 与跨 host handoff](https://learn.chatgpt.com/docs/remote-connections)
- [Computer Use：Windows 前台运行与本机 app policy](https://learn.chatgpt.com/docs/computer-use)
- [Codex worktree 与 Local/Worktree handoff](https://learn.chatgpt.com/docs/environments/git-worktrees)
