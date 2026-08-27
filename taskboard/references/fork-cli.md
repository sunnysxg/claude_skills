# taskctl：本 fork 独有的命令与参数

[cli.md](cli.md) 是上游原文，保持不动以便对照上游 diff。我们自己加的命令和参数写在这里。

## 全局参数

```
--agent codex|claude
```

写入方标识，决定看板画哪个图标、「查看对话」用哪种深链打开。不传时自动判：有
`CODEX_THREAD_ID` 记 codex，有 `CLAUDE_CODE_SESSION_ID` 记 claude，都没有默认 codex。
所以 Cursor 这类两个变量都取不到的环境必须显式带 `--agent claude`，否则会被记成 Codex。

## 推进方式

```
taskctl issue create ... --mode deliver|discuss
taskctl issue update ID --mode deliver|discuss
```

设卡片字段 `advanceMode`，不传 = `deliver`。语义见 SKILL.md「推进方式」。

## 目的地

```
taskctl issue create ... --destination production|dev
```

设卡片字段 `destination`，不传 = `production`（项目级默认可配）。**只在建卡时可设**——
`issue update` 改这个字段的 agent 来源写入会被服务端拒绝，觉得该改就评论提议。语义见 SKILL.md
「目的地」。

## 自动派发

```
taskctl dispatch status [--json]
taskctl dispatch enable  <项目 id> [--agent claude|codex] [--merge auto|main]
                                   [--post-merge <命令>] [--deploy <命令>]
taskctl dispatch disable <项目 id>
taskctl dispatch tick
taskctl dispatch stop <运行 id>
```

按项目开关。配置与护栏落在生产数据目录的 `dispatch.json`，改了即生效。`status` 里的
`integration` 说明晋升为什么暂停，`pendingDeploys` 是排队中或正在跑的部署。

todo_hub 自己的偏好：

```
--post-merge "npm --prefix dashi-taskboard run build:web"
--deploy "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/board.ps1 deploy"
```

## 收尾确认（ACK）

```
taskctl dispatch closeout ack <卡号> --delivery-id <delivery id>
```

开发卡进 `done` 后，看板把这条命令连同一个精确的 delivery id 投回原会话。**只在本对话实际收到
系统指令后原样执行**，不猜、不复用、不从别处抄——服务端会校验卡、原会话的 agent 与 session、
候选树／分支，以及当前 HEAD 是否干净且为冻结 HEAD 的后代，对不上直接拒。

ACK 本身不改卡状态、不 merge、不 push。ACK 之后由派发器负责落位、push、部署和收树。
