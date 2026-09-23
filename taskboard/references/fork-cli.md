# taskctl：本 fork 的命令参考在 help 里

本 fork 的命令、参数、取值与分区判据以 taskctl 自己打印的为准，用到哪条现查哪条：

```
taskctl help                   全部子命令、全局选项（--agent 自动判定）、退出码
taskctl help <资源> [动作]     一条子命令的参数、取值与本 fork 独有语义，如 taskctl help issue create
taskctl help statuses          分区判据表
```

help 从 taskctl 的解析表与 todo_hub `dashi-taskboard/shared/` 的语义模块现生成，快层用例钉住
两边一致，所以本文件不再手抄任何命令或参数。下面只留 help 打印不了的几句：

- **与 [cli.md](cli.md) 冲突时以 help 为准。** cli.md 是 dashi 上游原文，保持不动只为对照上游
  diff，不随本 fork 更新（例：它说挂关系会改写卡的 `threadId`，本 fork 不会）。help 打印不了
  这句，因为 cli.md 是本 skill 仓里的文件，taskctl 不知道它存在。
- **help 与看板实际行为对不上，改的是 todo_hub**（解析表旁的 `dashi-taskboard/cli/taskctl-help.mjs`
  或语义模块），不在本 skill 补写、也不开 claude_skills 对齐卡。这是维护分工，不是命令语义，
  help 里没有位置写。
- **派发器实现细节不在 help 里**：定时写法的变体（`T` 分隔、带秒、只写日期）与 `scheduled` hold
  在派发器闸门里的顺序，事实源是 todo_hub `dashi-taskboard/shared/task-schedule.mjs` 与
  `docs/agent/dispatch.md`「卡级定时」。help 只描述 CLI 收什么，不描述派发器怎么排。
