# Project Configuration

项目级、跨 agent 的已确认配置登记册。只记录需要长期复用的决定；不记录临时任务状态、
密钥、token 或机器私有路径。

## Git workflow

- commit: 用户明确要求时执行；一次要求覆盖本轮连续、相关的改动，不延伸到新任务
- push: 仅在用户明确要求时执行
- branch: 沿用仓库现有分支流程；需要新建或切换时询问
- pull_request: 沿用仓库现有流程；仅在用户明确要求时创建
- commit_message: `[模块][Tag] 中文摘要`，模板见 `git-workflow/references/git.md`；
  本仓库模块名见 `conventions.md` 第 11 节
- source: 用户确认
- recorded: 2026-08-04
