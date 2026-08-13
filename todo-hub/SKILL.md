---
name: todo-hub
description: 扫描所有项目的 _sxg/TODO.md，现扫现生成全局待办面板（文本或 HTML）：每项目未完成/高优计数、高优条目、格式漂移警告。用户想总览各项目待办、选从哪开工，或 agent 改共享组件前要查它所在项目的挂账时使用。
---

# todo-hub — 全局待办面板

事实源永远是各项目自己的 `_sxg/TODO.md`；面板是**现扫现生成的视图**，不落盘为事实、
不缓存、不双录。条目语法与跨项目写入约定见 `conventions.md` 第 12 节，本 skill 的
扫描器与其同步维护。

## 运行

```
python {本 skill 目录}/scripts/scan.py            # 文本面板到 stdout
python {本 skill 目录}/scripts/scan.py --html     # 另写 ~/_sxg/todo_hub/panel.html
```

- 仅 Python 标准库，无依赖；Windows 用 `python`，Linux 用 `python3`。
- 默认扫描 `~/Projects/**/_sxg/TODO.md`，自动发现，新项目建了 TODO 即入网。
- playground 容器（COMMON 的「项目包」条款）内的项目自动分组缩进展示。
- 本机额外源在本目录 `sources.local.json` 登记（gitignored，机器私有）：
  `{"roots": ["~/Other"], "files": ["~/somewhere/TODO.md"]}`；源不可达时面板
  标注降级，不中断。

## agent 使用约定

- 用户要看面板：直接跑脚本，把文本输出原样给用户（不要转述改写）。
- **改共享组件（某个 skill、全局规则）前**：先读它所在项目（通常是 claude_skills）
  的 `_sxg/TODO.md`，看有没有挂在该组件上的需求，一并考虑。
- 在 A 项目发现 B 项目该做的事：**直接写进 B 的 `_sxg/TODO.md`**（信箱直投，
  来龙去脉写进条目正文）；B 在别的机器或不知在哪时，自然语言记在 A 自己的 TODO 里。

## 尚未实现（挂起，等用户启动）

- sera 机器上的源（QuantResearch 等）与 vault `_hermes/todos.md`（须走 vault-ops
  SOP 读取；该文件是用户和 Hermes 共用的自由格式，**不得改造**，接入时做只读适配）。
- 面板局域网静态托管 + 计划任务定时刷新（HTML 输出已就绪，挂任务等用户验收后）。
- 飞书推送出口。
