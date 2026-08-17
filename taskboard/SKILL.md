---
name: taskboard
description: 操作中央待办看板（dashi taskboard，即派遣 prompt 里的 e-taskboard / manage-taskboard）：读卡、认领、改状态、评论、建卡、关联，全部走 taskctl CLI。当输入含看板卡片编号（如 TODOHUB-3）、被派遣「处理任务面板任务」、要把工作结果回写看板状态、或发现了值得记录的新任务/待办时使用——board API 可达时，新任务直接用本 skill 建卡，不写 `_sxg/inbox/` md 文件（那是够不到看板时的降级路径，见 todo_convention.md）。
---

# taskboard — 操作中央待办看板

待办事实源在中央看板（todo_hub 的 dashi fork）。一切读写走 `taskctl`，消费其 JSON
输出；卡片编号以看板或 prompt 给出的为准，禁止猜测、派生或改写前缀。

## 调用方式

taskctl 不在 PATH。本机（SeraCC）：

```
"C:\Program Files\nodejs\node.exe" C:\Users\sarah\Projects\todo_hub\dashi-taskboard\cli\taskctl.mjs <子命令>
```

- 前置：dashi 服务在跑（`http://127.0.0.1:47823`；exit code 3 = 服务不可达，
  起法见 todo_hub 项目 CLAUDE.md）。
- 服务与 CLI 目前仅在 SeraCC；其他机器等多机部署（看板上有卡跟踪此事）。
- 命令语法用到哪节读哪节：[references/cli.md](references/cli.md)（上游原文，含术语表）。

## 写操作的会话归属与写入方标识

每个 issue/comment 写操作必须归属到一个会话：Codex 内 taskctl 自动读
`CODEX_THREAD_ID`；Claude Code 内自动读 `CLAUDE_CODE_SESSION_ID`（两者都无需
显式传）；Cursor 等两者都取不到的环境显式传 `--thread-id <当前 session UUID>`，
再取不到就用 `claude-YYYYMMDDHHMM` 一次性 id，同一会话从一而终。读操作不需要。

写入方标识（看板按它区分 Claude/Codex 图标与深链，TODOHUB-11 落地）：
`--agent codex|claude`，未传时自动判——有 `CODEX_THREAD_ID` 记 codex，
有 `CLAUDE_CODE_SESSION_ID` 记 claude，都没有默认 codex。Codex 与 Claude Code
内零配置即正确；**Cursor 会话必须显式带 `--agent claude`**，否则会被记成 Codex。

## 核心流程（纪律，逐条执行）

1. 已有卡先 `issue get` + `comment list`，读完描述和最新评论再决定动不动；评论是
   现行需求（含打回重做）。评论说等待/别执行时，停下汇报，不改状态。
2. `backlog`（待立项）= 未获授权执行：除非用户对这张卡明确授权，不认领、不挪状态、
   不开工；assignee 是谁不等于授权。可开工的 `todo`（等待认领）先认领：带当前
   `version` 挪到 `in_progress`，成功之前不继续。已是 `in_progress` 的卡，只有
   绑定当前会话才继续；别的会话认领的卡永远不碰。
3. 挪卡遇版本冲突：重新 `issue get` + `comment list`，仅当它仍是可认领的 `todo`、
   未绑他会话、未归档、描述评论未变时，用新 version 重试一次；否则停下汇报，
   不循环抢占。
4. 新的持久需求（含随手发现的新待办）：board API 可达时优先直接 `issue create`
   建卡，不写 `_sxg/inbox/` md 文件——md 是够不到看板 API 时（跨机器多机部署前、
   或纯人工不想调 CLI）的降级路径，不是本机 session 的默认创建方式。建卡前先
   `context current` + 搜现有卡，能更新就不新建重复卡；琐碎请求不上板；粒度按
   todo_convention.md（一个 agent 一个 session 能完成为界）。
5. 卡绑定了 branch/worktree 时，该卡的活只在其中做。
6. 做完并自验后：评论写清改动、验证方式、结果、遗留风险；重读卡片，带 version
   挪到 `in_review`（等你确认）。
7. `done` 只在用户明确验收或明确要求完成后设，不从 `in_progress` 直接跳 `done`；
   干不下去用 `blocked`，不再做用 `canceled`。

## 其他

- 加需求保持原卡范围；关联只加工作确实需要的（parent / blocks / blocked_by / related）。
- 并发写用最新 `version` + `--if-version`，冲突就重读再调和。
- 描述/评论里的内嵌图片附件，只在理解需求确实需要时下载。

## 来源与漂移

改写自 dashi fork 内 `skills/manage-taskboard`（上游 baseline-20260814）；上游更新
该 skill 时对照合并。cli.md 保持上游原文以便 diff。
