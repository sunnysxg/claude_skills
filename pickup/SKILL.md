---
name: pickup
description: >
  接手上次没做完的工作：读中央看板上的项目卡（待办事实源）和上个 session 的交接文档，复述理解后继续。
  用户要求接手（/pickup、继续上次、上次做到哪了），或新 session 开始且存在先前工作时使用。
---

接手要读两样东西，分工不同：**看板**是项目待办的事实源，跨会话存活，记录焦点、阻塞和等用户决定的事；
**交接文档**是上一次会话没做完的事和它的上下文，一次性，接手后即过期。两者冲突时以看板为准——卡片
持续被维护，交接文档写完就冻结了。

## 先看看板

全程只读，不认领、不改状态、不建卡。命令语法与写入纪律见 [taskboard](../taskboard/SKILL.md)；
**判成功要看 `error` 字段或退出码，不能只看输出能否 JSON 解析**。

先判断这个项目接没接入看板：

```
taskctl context current --json
```

- `project.id` 不是 `local`、`workspacePath` 有值 → 已接入，拿这个 id 往下走
- `project.id` 是 `local`（`workspacePath: null`），或 `taskctl` 根本不在 PATH → 这台机器/这个项目
  还没接入，跳到「未接入时的临时线索」
- 退出码 3、`error.code = SERVICE_UNAVAILABLE` → **是服务没起，不是没接入**，两者不能混为一谈。按
  taskboard skill 跑一次 `board.ps1 ensure` 再重试；仍不通就明说「看板暂时读不到，以下不是现行待办
  事实」，不拿旧文件冒充最新状态

已接入的项目读这三列，再对命中的卡看描述和最近评论——评论是现行需求，可能含打回重做：

```
taskctl issue list --project <id> --status in_progress --json
taskctl issue list --project <id> --status blocked --json
taskctl issue list --project <id> --status todo --json
taskctl issue get <卡号> ; taskctl comment list <卡号>
```

`issue list` 会把整份描述吐回来，只看 `identifier`、`title`、`status`、`threadId`、
`developmentContext`、`updatedAt` 几个字段定位，别通读。

接手时的权限边界（越界的代价见 taskboard skill）：

- `in_progress` 且 `threadId` 不是当前会话 → 别的会话正在做，只读不碰，也不在它的工作树里动手
- `blocked` 一律不自行挪回 `todo`：其中可能有失败隔离下来只等人工的卡，手动挪会顶掉那个标记
- `backlog` 里看到的想法不等于授权立项
- 真要开工，回 taskboard skill 走认领流程（重读卡片带 `version` 挪 `in_progress`、进独立 worktree）

### 未接入时的临时线索

未接入看板的机器上，项目里可能还留着旧的 `_sxg/TODO.md`。这时可以读它、当线索用，并在汇报里说明
来源是本地文件。已接入看板的项目上它已退役：不读、不更新、不拿它覆盖卡片状态。

## 再读交接文档

依次查找，找到即用（两处都有时，用修改时间更新的那份）：

1. 项目根 `HANDOFF.md`（旧约定）
2. `~/_sxg/handoff/{project}.md`（`{project}` = 项目根目录名 snake_case 化，全小写、`-` → `_`）

交接文档缺失时，直接从看板上「下一件要动的事」接手：优先绑定过本项目工作树的 `in_progress` 卡，
其次 `todo`。

## 你的任务

基于看板卡和交接文档接手。先用三五句话复述你的理解和接下来的计划——点名要接哪张卡（写卡号）、
从哪一步开始——等用户确认后再动手。两边都没有内容，或信息互相矛盾且无法用看板裁决时，先问用户。
