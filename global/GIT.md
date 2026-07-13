# Git 工作流与提交规范

跨项目通用。Claude Code / Cursor 等均适用。新 session 必读（见 `read-context`）。
项目内 `CLAUDE.md` 若定义了 **模块前缀**（如 `[Calc]`），与本文件一并生效，冲突时以项目内为准。

---

## 1. 工作流

```
功能改动完成 → 请用户验收功能 → OK → 一句话收尾 → 用户说「提交」→ commit → 用户说 push → push
```

### 1.1 功能验收

- 有代码/配置/文档**实质改动**时，先让用户确认**功能是否正确**（行为、结果是否符合预期）。
- **不是**验收 commit message 文案。
- 纯问答、代码审查、只读探索：**不碰 git**。

### 1.2 对用户收尾

- 功能 OK 后，用**一行**说明改了什么、实现什么（粒度 ≈ commit 首行）。
- **不要**贴完整 diff、不要列多 commit 拆分表当作主要汇报内容。

示例：

> 已在 `session_resolve.py` 实现同 chat 重复 `/session-log` 时 update 同文件；请你看下是否符合预期。

用户确认后，可补一句：

> 可 `[session-log][Feat] Cursor upsert` 提交；需要 push 请说。

### 1.3 默认权限

| 操作 | 默认 |
|------|------|
| `git commit` | **仅**用户明确说「提交 / commit / 提交上去」等 |
| `git push` | **仅**用户明确说 push / 推送 |
| Agent 内部 | 可自行 `git status`、`git diff`、`git log`、拆 commit、拟 message；不必全部展示 |

### 1.4 多仓库

- **项目仓库**与 **`~/.claude/skills`** 分开准备、分开提交，**不混在一个 commit**。
- 不确定仓库惯例（直接 push main vs 开 PR）时，问用户。

### 1.5 与其他 skill 的边界

| 工具 | 关系 |
|------|------|
| `session-log` | 只把**已有** commit hash 写入摘要 |
| `handoff` | 不写 git 操作 |
| `split-to-prs` | 分 PR 场景：用户批准计划前**禁止** commit/push；staging 细节以该 skill 为准 |

---

## 2. Commit 消息格式

首行 `[模块][Tag] 中文摘要`；空一行；正文 1～3 句（为什么改、影响什么）。**全部用中文。**
默认不加 Co-authored-by；PR 标题可与 commit 首行相同。

```
[Calc][Feat] 启动时从 factorhub 同步 registry

运行时导出 fields/operators 至 gitignore 的 artifacts/doc；
移除 vendor 内嵌 CSV；支持 FACTORHUB_ROOT 覆盖。
```

### 2.1 模块

标明改动所在子目录/域：

- 各项目在自己的 `CLAUDE.md` 里定义前缀表；**没有定义时**按该项目目录名自拟。
- `Repo` = 仓库级（git 结构、目录搬迁、README/CLAUDE）
- `Doc` = 仅文档
- `~/.claude/skills` 仓库：模块名用 **skill 目录名**（如 `[session-log]`、`[global]`），见 `conventions.md`

**项目模块前缀示例**（详细表以各项目 CLAUDE 为准）：

| 项目 | 前缀示例 |
|------|----------|
| FactorInfra DSL | `[Calc]` `[Mat]` `[Vis]` `[Repo]` |
| FactorInfra Evaluate | `[Eval]` |
| claude_skills | `[session-log]` `[global]` 等 |

### 2.2 Tag

| Tag | 含义 |
|-----|------|
| `Init` | 首次导入（少用） |
| `Feat` | 新功能 |
| `Fix` | 修 bug |
| `Ref` | 重构（对外行为不变） |
| `Docs` | 只改文档 |
| `Chore` | 合并、gitignore、杂项维护 |

摘要一行说完意图；正文写原因与范围，不写空话。

---

## 3. 执行 commit

用户说「提交」后：

1. 并行：`git status`、`git diff`（含 staged/unstaged）、`git log -3`（对齐仓库 commit 风格）
2. 只 stage **相关**文件；避免 `git add .` / `git add -A`（分 PR 场景尤其如此）
3. 用 HEREDOC 写 message：

```bash
git commit -m "$(cat <<'EOF'
[模块][Tag] 中文摘要

正文 1～3 句。
EOF
)"
```

4. commit 后 `git status` 确认成功
5. **不要**提交可能含 secrets 的文件（`.env`、credentials 等）；若用户坚持，先警告

### 3.1 amend 与 hook

- hook 失败或 reject：**修问题后新建 commit**，不要 amend（除非下面三条件**全满足**）：
  1. 用户明确要求 amend，**或** commit 成功但 hook 自动改了文件需纳入
  2. HEAD 是**本 session**刚创建的 commit
  3. **尚未 push** 到 remote
- 已 push 后：**不要** amend（除非用户明确要求且接受 force push）
- **禁止** `--no-verify` / `--no-gpg-sign`，除非用户明确要求

---

## 4. Push 与 PR

- **push 与 commit 分离**：用户说 push 才 push
- **禁止** `git push --force` 到 main/master；若用户要求，先警告
- **禁止**修改 git config
- 开 PR：Cursor 侧可用 `gh pr create`（完整步骤见 Cursor User Rules）；决策流程以本节为准

---

## 5. 安全红线（摘要）

- 不改 `git config`
- 不 force push main/master（除非用户明确接受风险）
- 不提交 secrets
- 不 skip hooks（除非用户明确要求）
- 不用破坏性命令（`reset --hard`、`clean -fdx`、删分支、改历史）除非用户明确批准
