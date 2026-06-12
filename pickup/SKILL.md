---
name: pickup
description: >
  读取上一个 session 留下的 HANDOFF.md 并接手继续。
  MUST trigger when the user says: "/pickup", "接手", "继续上次", "从哪里开始",
  "上次做到哪了", or at the start of a new session when prior work exists.
---

## 上次的交接文档

读取当前工作目录下的 HANDOFF.md（`cat HANDOFF.md 2>/dev/null`）。

## 你的任务

基于上面的交接文档接手。先用三五句话复述你的理解和接下来的计划，等用户确认后再动手。如果文档缺失或不完整，先问用户。
