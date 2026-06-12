---
name: handoff
description: >
  把剩余任务和必要上下文写成交接文档，供下个 session/agent 接手。
  MUST trigger when the user says: "/handoff", "交接", "写交接", "context快满了",
  "下个session继续", "留个文档", or when context is running low and work remains.
---

当前上下文快满了，不要继续写代码。把交接信息写入仓库根目录 HANDOFF.md：
1. 原始目标 / 需求
2. 已完成部分（带文件路径）
3. 剩余工作，写成可执行的下一步
4. 关键决策、约束、坑、未决问题
5. 如何运行 / 验证
写得自包含，让没有任何上下文的 agent 也能续上。写完停下并告诉我路径。
