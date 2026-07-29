# Project Configuration

项目级、跨 agent 的已确认配置登记册。只记录需要长期复用的决定；不记录临时任务状态、
密钥、token 或机器私有路径。

## Git workflow

- commit: 每个已获用户授权、验证通过的 skill 改动形成独立 commit，无需再次询问
- push: 仅在用户明确要求时执行
- branch_pr: 沿用仓库现有分支与 PR 流程
- commit_message: 遵循 `conventions.md`
- source: 用户确认
- recorded: 2026-07-29
