---
name: git-workflow
description: >
  执行 Git 写操作及相关远端变更，包括 stage、commit、amend、merge/rebase、分支或 tag 变更、
  push 和创建 PR。任何任务即将改变本地仓库、提交历史或远端状态时使用；纯 status/diff/log 不使用。
---

# Git Workflow

当前任务首次执行 Git 写操作前，完整读取 [references/git.md](references/git.md)。同一任务后续
操作复用已加载内容，不重复读取；新任务、上下文压缩后或 reference 已变更时重新读取。

项目规范以项目指令文件（`AGENTS.md`、`CLAUDE.md`）里的 Git 规则为准；没有规则时按
reference 的保守默认执行，完成后问一次是否放宽并记录。
