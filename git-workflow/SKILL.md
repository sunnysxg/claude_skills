---
name: git-workflow
description: >
  按 GIT.md 执行 commit/push：功能验收后用户说提交或推送时使用。
  完整规则在 ~/.claude/skills/global/GIT.md；本 session 若已读过则直接执行，勿重复 Read。
disable-model-invocation: true
---

# Git Workflow

**正文 SSOT**：`~/.claude/skills/global/GIT.md`（新 session 已由 `read-context` 必读）。

1. 若本 session **已读过** GIT.md → **直接按其中流程执行**，不要再 Read 全文。
2. 若不确定是否读过（如新 agent、context 已压缩）→ Read `~/.claude/skills/global/GIT.md` 后再执行。
3. **不要**在本文件重复 GIT.md 内容。

用户说「提交 / commit」→ 按 GIT.md §3 执行 commit。  
用户说「push / 推送」→ 按 GIT.md §4 执行 push。
