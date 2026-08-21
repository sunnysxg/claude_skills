# Git 工作流

Git 的目标不是制造提交记录，而是让改动可理解、可验证、可回退，并按项目约定安全地同步。

目录：[项目规范](#1-先确认项目规范) · [执行节奏](#2-执行节奏) · [Commit](#3-commit) ·
[Push、分支与 PR](#4-push分支与-pr) · [安全边界](#5-安全边界) ·
[Worktree 与并行任务](#6-worktree-与并行任务)

## 1. 先确认项目规范

项目规范就是项目指令文件（`AGENTS.md`、`CLAUDE.md` 及其明确引用的开发文档）里的 Git 规则。
这些文件随会话自动加载，不需要额外搜索，也不要把它们复制到别处再读。

用户在当前任务中的明确指令覆盖本次操作；只有用户确认它是长期规范时，才写进项目指令文件。
规则冲突时以范围更具体、由用户明确确认的为准，无法判断时只询问会影响当前操作的那一点。

项目指令里没有 Git 规则时，按第 2 节的默认值执行本次操作，不要在动手前抛出一张配置表让
用户先做一遍配置。本次操作完成后问一次：

> 这个项目还没有 Git 规范，我按默认执行：commit 和 push 都等你明确要求。要放宽哪一项吗？
> 你的答复我会记进 `AGENTS.md`。

用户答复后，把结论逐项写进项目指令文件；两个文件都没有时新建 `AGENTS.md`，只写这一段。
之后不再就同一项询问。逐项说明每个操作由谁决定、何时执行：

```markdown
- commit: 何时执行、由谁决定
- push: 何时执行、由谁决定
- branch: 分支创建与切换规则
- pull_request: PR 创建与合并规则
- commit_message: 采用的 message 格式
```

## 2. 执行节奏

授权逐项判断，不使用「按需」「宽松」「混合」这类整体等级。项目配置未定义的字段按下面的
默认值执行，不自行放宽：

- commit：用户明确要求时执行。一次要求覆盖本轮连续、相关的改动，不延伸到之后的新任务。
- push：用户明确要求时执行。commit 与 push 是两次独立授权。
- branch：沿用当前分支；需要新建或切换时先询问。
- pull_request：用户明确要求时创建。

项目配置已放宽某一项时按配置执行，不再逐次询问。放宽后的节奏：

- 一个可独立理解、回退且验证通过的改动形成一个 commit。
- 在高风险改动前、阶段完成后、交接或切换任务前形成清晰检查点。
- 不为每次微小保存制造 checkpoint commit，也不把无关改动混在一起。
- push 合并到阶段完成、会话收尾、交接或跨设备同步前；测试失败或工作尚不完整时不推送。

用户对某次操作的直接指令只授权该次操作，除非用户同时把它确认为项目长期规范并更新配置。

## 3. Commit

有实质改动时，先让用户验收功能是否符合预期，再进入 commit；验收的是行为和结果，不是
message 文案。纯问答、代码审查和只读探索不进入 Git 流程。

执行 commit 前：

1. 检查 `git status`、staged/unstaged diff 和最近提交，确认仓库状态与 message 风格。
2. 区分本次改动、用户已有改动和无关文件；只 stage 本次相关的明确路径，不用
   `git add .` 或 `git add -A`。
3. 运行与改动风险相称的验证。失败时修复根因，不靠跳过检查制造成功。
4. 检查待提交文件是否可能包含 secrets、凭据或机器私有配置。

提交后再次检查状态并向用户报告 commit 摘要与短 hash。

### Commit message

格式按优先级取：项目配置中指定的格式，其次仓库近期稳定使用的格式，都没有时用下面的默认
模板，并在首次使用时告知用户、记录到项目配置。

```text
[模块][Tag] 中文摘要

正文 1～3 句，说明为什么改、影响什么。
```

- 摘要一行说完改动意图；正文只在有助于理解原因和影响时添加，不写空话。
- 默认全部使用中文，默认不添加 `Co-authored-by`。
- PR 标题可以与 commit 摘要相同。
- 模块名标明改动所在的子目录或领域。项目定义了前缀表时以项目为准；没有定义时按目录名
  自拟，并把结果记录到项目配置，避免同一项目每次取名不同。

| Tag | 含义 |
|-----|------|
| `Init` | 首次导入，少用 |
| `Feat` | 新功能 |
| `Fix` | 修复问题 |
| `Ref` | 重构，对外行为不变 |
| `Docs` | 仅文档 |
| `Chore` | 仓库维护、配置和杂项 |

### Amend 与 hooks

- Hook 或检查失败时修复问题，再创建新 commit。
- 只有用户明确要求 amend，或本次刚创建的未推送 commit 被 hook 自动修改文件时，才考虑 amend。
- 已推送的 commit 不 amend，除非用户明确授权历史重写及其风险。
- 不用 `--no-verify`、`--no-gpg-sign` 绕过检查，除非用户针对该风险明确授权。

## 4. Push、分支与 PR

执行 push 前检查当前分支、upstream、待推送 commits 和工作区状态，并遵守项目的分支/PR
流程。没有 upstream、目标分支不明确或会触发未经约定的发布流程时，先询问。

- 不 force push `main` / `master`。
- 其他分支需要历史重写时，先取得明确授权并优先使用 `--force-with-lease`。
- 不擅自修改 `git config`。
- PR 的创建时机、标题和合并方式以项目规范为准。

### 远端连接

- GitHub 远端统一用 HTTPS（`https://github.com/<owner>/<repo>.git`），凭据交给 Git Credential
  Manager（GCM，Git for Windows 自带，`credential.helper=manager`）；新机器首次在交互终端跑
  `git credential-manager github login` 走一次浏览器授权即可，之后免交互。原因有二：① 失败单元
  小——SSH 一次 push 是一条长会话，代理链中途掐一下整个操作作废且 ssh 无应用层重试；HTTPS 是
  几个独立短请求，掐掉一个 curl 自动换连接重发（实测链路对两者掐的概率相当，差别在能否自愈）；
  ② 它吃系统代理——SSH 不吃系统代理和 `HTTP(S)_PROXY`，只有开了 TUN（虚拟网卡全接管）的机器
  SSH 才走代理，仅系统代理模式的机器（如无影云）`git@` 远端是直连，境内连 GitHub 天然不稳。
  发现仓库还是 `git@github.com:` 远端时用 `git remote set-url origin <https url>` 切过来。
- 经代理链推送的机器（vmcc）全局设 `git config --global http.extraHeader "Connection: close"`：
  默认 curl 复用 `GET info/refs` 的连接发 `POST git-receive-pack`，这条复用连接上的 POST 约一半
  会在回包前被链路掐断，curl 当作陈旧连接自动重发、撞上已生效的自己，于是报
  `cannot lock ref ... is at <刚提交的 hash>` 且 rc=1——推送其实已落地（`git fetch` 核实即可，
  不要再推、更不要 force）。逐请求新建连接后 10/10 干净，代价是每次 push 多两次 TLS 握手。
  只开系统代理的机器（无影云）另需 `http.proxy http://127.0.0.1:<混合端口>`（libcurl 不读
  Windows 系统代理设置）。
- push/fetch/pull 报 `Connection closed / reset / timed out` 时先原样重试 1～2 次再诊断：
  代理链瞬断是常态，重试即愈的失败不代表配置、凭据或权限坏了；连续几分钟都失败通常是整条
  代理链劣化，等链路恢复，不要改配置。

## 5. 安全边界

- 不提交 secrets、credentials、私钥或不应共享的机器配置。
- 不覆盖、丢弃或夹带用户已有改动。
- 不执行 `reset --hard`、`clean -fdx`、删分支、重写历史等破坏性操作，除非用户明确批准
  具体目标和风险。
- 多仓库改动分别检查、验证和提交，不混成一个无法独立回退的工作单元。

## 6. Worktree 与并行任务

- 并行的改代码任务各用独立 worktree + 独立分支，两个 agent 不写同一 checkout；主检出
  有他人未提交改动时不在主检出动手，开自己的 worktree。
- 优先用托管机制，两个主入口都能指定名字，托管与命名不冲突：会话内开树用 `EnterWorktree`
  传 `name`，起新会话用 CLI `claude --worktree <名字>`（`-w, --worktree [name]`）。托管不可用
  或需要指定基线时手工建 `git worktree add .claude/worktrees/<名字> -b <分支名> <基线>`，
  再用 `EnterWorktree` 的 `path` 进去——这样进的树 `ExitWorktree` 不删（只会 `keep`），收树
  走下面手工那条。
- 树名 = 任务标识 + 随机后缀（如 `TODOHUB-38-a1b2c3`），不用默认随机名（名字不传才随机）：
  每段限字母数字点下划线短横（大小写都收，卡号原样抄，不转小写）、总长 ≤64；`EnterWorktree`
  建的分支自动为 `worktree-<name>`（`Agent` 的 isolation 树才是 `claude/<name>`）。唯一不给
  命名口子的通道是 `Agent` 工具的 `isolation: "worktree"`，因此不用它派活——要并行就在待办
  看板建卡，由新会话认领（taskboard skill）。
- 会话一开局就已在托管树里、名字已定的，不改名。
- 树的生命周期 = 任务的生命周期。任务「完成」的定义包含成果已合并回主分支或已开 PR，
  不允许成果只停在 worktree 分支上；合并后当场收树，不留给「下个会话」——会话被
  archive 或非正常退出时收尾链根本不跑。
- 收树 = 清三样：磁盘目录、主仓 `.git/worktrees/<名字>/` 登记、分支。按人在哪儿选做法：

  | 处境 | 做法 |
  |---|---|
  | 人在自己的托管树里 | `ExitWorktree` 传 `action: "remove"`：一步清三样并把 cwd 还回原目录。有未提交改动或未合并提交时它会拒绝并列出，确认后才加 `discard_changes: true` |
  | 人在主检出，收别的会话留下的树 | `git worktree remove <路径>` 清目录与登记，再 `git branch -d <分支>` |
  | 目录已消失，或被进程占住删不掉 | `git worktree prune` 清登记（只扫 `.git/worktrees/`，把指向已不存在目录的登记删掉；不动磁盘、不动分支），再 `git branch -D <分支>` |

  判据是 `git worktree list` 不再列出它 = 收干净了。磁盘上剩的空目录无害（常见于目录被
  某进程当 cwd 占着，Windows 上会报 `Device or resource busy`），留着，等该进程退出再删。
  收树前先停掉树里跑着的服务，并解掉树内指向仓外的链接——Windows junction（如复用主仓
  `node_modules` 的 `mklink /J`）要 `cmd /c rmdir <链接路径>` 单删链接本身，否则删树可能
  递归进链接目标。
- 不用 `rm -rf` 删树目录。人在自己树里时也不用 `git worktree remove`：托管树在 `worktree list`
  里带 `locked` 标记，git 会直接拒绝；且 cwd 被 harness 每次工具调用重锚回树里，恒
  Permission denied。
- 同一仓库并行 worktree 默认不超过 8 个（含托管创建的与看板自动派发建的）；超限先收完成的树
  再开新的。项目指令文件可覆盖此上限。
- 发现陈旧树（基线过老或带未提交改动）不静默删除，报告给用户——脏树里可能是别的
  会话未完成的活。
