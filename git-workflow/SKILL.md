---
name: git-workflow
description: >
  管理 Git 提交、推送、分支和 PR。用户要求提交或推送，或项目规范授权 agent 按约定节奏执行
  Git 写操作时使用；先遵守项目规范，缺失时询问并记录到项目配置后再执行。
---

# Git Workflow

执行 Git 写操作前，完整读取 [references/git.md](references/git.md)，按其中顺序解析项目规范、
授权范围、执行节奏和安全边界。

只读的 `status`、`diff`、`log` 可用于确认现状，不视为 Git 写操作。项目没有规范时，先提出
最小必要建议，获得用户确认并记录；不要凭通用偏好替项目决定 commit、push 或 PR 节奏。
