# 跨设备、跨客户端同步设计

本文定义两台 Windows 电脑与 Linux host 上的 ChatGPT/Codex、Claude Code、Cursor 与
OpenCode 如何共享公共 skills，同时保留每台机器的认证、网络和 GUI 权限边界。

## 1. 分层

| 层 | 解决的问题 | 是否进本仓库 |
|---|---|---|
| Git 公共层 | skills、manifest、跨平台规则、同步/检查脚本 | 是 |
| machine override | `machine_id`、客户端/skill 启用状态、非默认安装根 | 否，使用 `sync.local.json` |
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
客户端和支持平台，不通过扫描仓库目录猜测安装内容。每个 skill/alias 都必须声明
`platforms`；alias 还要声明 `canonical`，使 machine override 能同时控制 canonical 与旧名。
alias 只用于仍有真实调用方的短期迁移，迁移完成后从 manifest 删除。`mmdexplain` 已在
2026-07-27 退役，canonical 名称只有 `mmd-explain`。同步器没有 prune，因此曾安装过旧
alias 的机器需各自确认并删除旧链接；不能删除 canonical 源目录。

`managed_rules` 与 skill 清单并列，声明由 `global/COMMON.md` 生成的客户端规则投影。规则
投影不是 skill，也不是客户端根目录链接；它有独立的 DryRun、Doctor、冲突保护和统计。

链接建立成功不等于客户端一定能加载。`git-workflow` 已改为标准 Agent Skill，并安装到
Cursor 与 Codex；它在 Git 写操作前触发，项目规范以项目指令文件里的 Git 规则为准。
`session-log` 的 frontmatter 已标准化（移除了 Claude/Cursor 专属的
`disable-model-invocation`），剩余阻塞是脚本只解析 Cursor 与 Claude Code 的 transcript
格式；补齐 Codex transcript 解析与 upsert 后即可安装到 Codex。

## 3. Windows 使用方法

每台 Windows 机器各自创建不入 Git 的 override：

```powershell
Copy-Item sync.local.example.json sync.local.json
```

把 `machine_id` 改成稳定、易识别且不含凭据的名称，例如 `home-win`、`cloud-win`。未创建
override 时，脚本使用归一化 hostname。

可以只在某台机器关闭一个 canonical skill：

```json
{
  "skills": {
    "mmd-explain": {
      "enabled": false
    }
  }
}
```

同步器先按当前平台过滤 manifest，再应用本机 override。若未来为某个 canonical skill 临时
增加 alias，关闭 canonical 时 alias 也同时停止管理。同步器没有 prune 行为，所以不会删除
此前已存在的链接。

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
- 默认 `Scope=All`；`-Scope Skills` 只管理 skill 链接，`-Scope Rules` 只管理全局规则。
- Cursor 规则只写专用的 `~/.cursor/rules/claude-skills-common.mdc`；若同名文件存在但没有
  管理标记，报冲突且不覆盖。
- Codex 只替换 `~/.codex/AGENTS.md` 的管理区块，区块前后本机内容原样保留；缺失标记时
  追加，单侧/重复/逆序标记时报冲突。
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
`--client cursor` 等参数缩小客户端范围，用 `--scope skills` / `--scope rules` 缩小操作
类型。安全语义与 Windows 一致：

- 普通文件和真实目录永不覆盖。
- 正确 symlink 重复执行不变。
- 错误 symlink 默认报冲突，只有 `--repair-links` 才替换链接本身。
- 不扫描、删除或接管 manifest 之外的客户端专属目录。

旧 `scripts/sync_cursor_skills.sh` 只是一层兼容包装，内部调用 manifest 同步器。当前只支持并
验收 Linux，不宣称支持 macOS。

## 5. Skill 内的平台路由

安装过滤与运行时选择是两层：

1. manifest `platforms` 与 `sync.local.json` 决定这台机器是否安装该 skill。
2. skill 已安装后，公共 `SKILL.md` 识别当前系统，只加载对应平台 reference 和脚本。

`mmd-explain` 是第一项完整实现：

| 平台 | 只读 reference | doctor | renderer |
|---|---|---|---|
| Windows | `references/windows.md` | `scripts/doctor.ps1` | `scripts/render.ps1` |
| Linux | `references/linux.md` | `scripts/doctor.sh` | `scripts/render.sh` |

公共 `fonts.css` 同时列出 Noto 与 Windows 字体回退；系统不存在的字体由浏览器自然跳过。
Windows 自动探测 `mmdc`/`npx`/`pnpm`、Chrome/Edge/Brave、Microsoft YaHei 与 Segoe UI Emoji；
Linux 自动探测显式 renderer、conda、PATH 和 fontconfig。只有自动探测不够时才在本机设置
`MMD_EXPLAIN_MMDC`、`MMD_EXPLAIN_CONDA_ENV` 或 `PUPPETEER_EXECUTABLE_PATH`，这些值不入 Git。
若 Codex bundled `pnpm` 的配套 Node 不在 PATH，Windows adapter 只为当前渲染进程临时注入，
不写入机器级环境变量。

平台 reference 必须由公共 `SKILL.md` 直接链接，避免深层引用；agent 不读取或执行另一个
平台的安装步骤。未支持的平台只输出 `.mmd`，不得暗示 renderer 已验证。

## 6. COMMON 与全局指令

`global/COMMON.md` 是跨客户端规则的唯一维护源。客户端入口只做加载适配，不再各维护一份
正文：

| 客户端 | 入口 | 投影方式 | 本机内容边界 |
|---|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` → `skills/global/CLAUDE.md` | `global/CLAUDE.md` 仅用 `@COMMON.md` 相对导入 | 用户级入口导入行之外可追加本机规则 |
| Cursor 3.9.16+ | `~/.cursor/rules/claude-skills-common.mdc` | 同步器生成带 `alwaysApply: true` frontmatter 的用户文件规则 | 只接管这个专用文件，不碰同目录其他规则 |
| Codex | `~/.codex/AGENTS.md` | 同步器更新 `claude_skills:global-common` 标记区块 | 区块前后内容原样保留 |

Cursor 官方稳定入口仍是 Settings → Rules → User Rules；当前 vmcc 的 3.9.16 已确认实现
`~/.cursor/rules/*.mdc` 用户文件规则。同步器采用文件入口，便于从 COMMON 自动更新和
Doctor 比对；旧 Cursor 或云端环境若不加载它，应在官方 User Rules 中放一条读取 COMMON
的短规则，不能同时再复制整份正文，避免重复注入。

Codex 不解析 Claude 的 `@import`，所以不能让 `~/.codex/AGENTS.md` 只写
`@skills/global/...`。同步器会把 COMMON 正文复制进管理区块；历史上唯一一行
`@skills/global/AGENTS.md` 的旧占位会在精确匹配时迁移，若文件还有其他内容则不删除。

OpenCode 在未配置自己的 `~/.config/opencode/AGENTS.md` 时会回退到 Claude 用户规则，但它
不保证解析 Claude 的递归 `@import`；本机尚未安装 OpenCode，本切片不宣称已做运行时验收。
若以后启用，应在 manifest 增加独立 target 或通过 OpenCode `instructions` 直接指向 COMMON。

不要同步整份 `~/.codex/config.toml`。Codex 个人全局习惯放用户级 `AGENTS.md`，仓库规则放
作用域最接近项目的 `AGENTS.md`；两层一并生效。

Windows 的 managed-rule 隔离回归：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_sync_rules.ps1
```

覆盖首次创建、DryRun、Doctor 漂移、幂等不改 mtime、块外内容保留、精确旧占位迁移和
畸形/未受管文件冲突。Linux 同步器已实现对称状态机，但阶段 2 仍需在 Linux host 实机复验。

## 7. session-log 跨 host（后续切片）

当前本机能力已经覆盖 Cursor 与 Claude Code：`session_times.py` 自动识别两类 transcript，
`session_resolve.py` 按同一 session UUID upsert；可选 Stop hook
`auto_rename_on_stop.py` 在 tmux 会话中执行最终 `/rename`。hook 注册属于 machine-local
Claude/Cursor 配置，不由本仓库同步。以上能力仍只处理当前 host 的归档文件，并不等于跨 host
已经去重。

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

## 8. 并行写入约束

两个 agent 不得同时写同一 checkout。每个并行任务使用独立 worktree 和独立分支，通过 Git
commit/merge 协调。Handoff 可以在 Local、worktree 和匹配的 SSH host 项目间移动 task，但
同一分支不能同时 checkout 在两个 worktree。

## 9. 验收矩阵

| 场景 | 期望 | 本切片 |
|---|---|---|
| 两台 Windows 首次 `-DryRun` | 只报告将创建的 junction，不改磁盘 | 已实现 |
| 两台 Windows 正式 Sync 后 Doctor | 每个声明 skill 指向中央仓库，重复运行幂等 | 已实现 |
| 客户端已有真实目录 | 报冲突并保留原目录 | 已实现 |
| 现有错误 junction | 默认报冲突；`-RepairLinks` 才替换 | 已实现 |
| `mmdexplain` 别名退役 | manifest 只保留 canonical；旧链接不由 prune 自动删除 | vmcc 已清理；其他曾安装机器待各自清理 |
| Codex `.system`/插件缓存 | 不扫描、不删除、不覆盖 | 已实现 |
| 每机不同安装根/客户端组合 | untracked override 可改 root/enabled | 已实现 |
| skill 平台过滤 | Windows/Linux 只管理 manifest 中包含当前平台的条目 | 已实现并在两平台隔离 dry-run |
| 逐-skill machine override | 关闭 canonical 时 alias 同时停止管理；未知名称报错 | 已实现并在两平台隔离 dry-run |
| Linux 首次 dry-run | 报告 Cursor/Codex symlink 计划，不创建目录 | 已在 Linux host 实机验收，零冲突 |
| Linux Sync、Doctor、重复 Sync | 16 个 canonical skill 链接与 2 个规则投影分别通过，重复运行幂等 | 阶段 1 曾以含 alias 的 18/18 通过；阶段 2 待 Linux 复验 |
| Linux 冲突与修复 | 保留真实目录；错误 symlink 仅显式 repair | 已实现并在 Linux host 隔离验收 |
| Windows `mmd-explain` | doctor 探测浏览器/字体；真实 renderer 生成中文与 emoji 正常的 PNG | 已在当前 Windows host 用 bundled pnpm/Node 实机验收；第二台待执行 |
| Linux `mmd-explain` | doctor 通过；真实 conda renderer 生成中文与 emoji 正常的 PNG | 已在 Linux host `/tmp` 验收 |
| Linux `session-log` | Cursor/Claude 时间解析、upsert 与 Stop hook 去重 | 10 项回归测试已在 Windows 与 Linux 通过；Linux hook 已 machine-local 配置 |
| Codex skill 格式 | 只安装 Agent Skills 标准兼容项；`git-workflow` 已标准化，`session-log` 暂缓 | Git 已启用；session-log 待补 upsert 与调用策略 |
| Remote Control | 每个控制端与每个 host 单独配对；同账号不视为已配对 | 人工验收 |
| SSH host | key + 最小权限账户 + VPN/mesh；无公开 app-server listener | 人工验收 |
| Windows Computer Use | 在执行 host 前台运行，保持解锁；allowlist 不跨机 | 人工验收 |
| Git 敏感边界 | auth、私钥、`config.toml`、allowlist、Clash 运行期文件不入库 | 已设计，需 CI 检查 |
| COMMON → Claude adapter | 相对 import 只加载一份 COMMON | 已实现；新 Claude session 待行为验收 |
| COMMON → Cursor user file rule | 生成专用 alwaysApply `.mdc`，不接管其他规则 | Windows 27 项隔离断言与 vmcc Doctor 通过；新 Cursor task 待行为验收 |
| COMMON → Codex managed block | 更新公共区块且保留机器私有区块 | Windows 27 项隔离断言、vmcc Doctor 与重复 Sync 通过 |
| 同 task 跨 host session upsert | task ID 不变，记录 host history，私有传输后更新同一文件 | 需先定传输层 |
| 两个 agent 并行 | 独立 worktree/branch，不共写 checkout | 流程约束 |

## 10. 官方参考

- [Codex skills：保存位置、symlink 与渐进加载](https://learn.chatgpt.com/docs/build-skills)
- [Agent Skills 规范：SKILL.md frontmatter](https://agentskills.io/specification)
- [Codex Remote Control、SSH host 与跨 host handoff](https://learn.chatgpt.com/docs/remote-connections)
- [Computer Use：Windows 前台运行与本机 app policy](https://learn.chatgpt.com/docs/computer-use)
- [Codex worktree 与 Local/Worktree handoff](https://learn.chatgpt.com/docs/environments/git-worktrees)
- [Claude Code：CLAUDE.md 导入与相对路径解析](https://code.claude.com/docs/zh-CN/memory#importing-additional-files)
- [Cursor Rules：项目规则与全局 User Rules](https://docs.cursor.com/context/rules)
- [OpenCode Rules：全局文件、Claude fallback 与 instructions](https://opencode.ai/docs/rules/)
