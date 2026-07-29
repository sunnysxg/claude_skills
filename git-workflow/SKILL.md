---
name: git-workflow
description: >
  执行 Git 写操作及相关远端变更，包括 stage、commit、amend、merge/rebase、分支或 tag 变更、
  push 和创建 PR。任何任务即将改变本地仓库、提交历史或远端状态时使用；纯 status/diff/log 不使用。
---

# Git Workflow

当前任务首次执行 Git 写操作前，完整读取 [references/git.md](references/git.md)。同一任务后续
操作复用已加载内容，不重复读取；新任务、上下文压缩后或 reference 已变更时重新读取。

先读取项目 `_sxg/project_config.md` 的 `Git workflow`。该段落不存在时，按 reference
一次性解析项目规范、记录结果，再执行写操作。
