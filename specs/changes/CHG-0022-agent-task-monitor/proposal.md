---
kind: change-proposal
id: CHG-0022
status: in_progress
target: 0.1
date: 2026-08-01
implementation_status: in_progress
requirements:
  - TASK-001
  - TASK-002
  - TASK-003
  - TASK-004
---

# Agent 对话任务监视器与结构化选择

当前聊天工作区把所有复杂任务都呈现为一条回答，用户无法知道任务是否被拆分、当前
阶段是什么，也无法通过轻量选择卡回答 Agent 的澄清问题。本变更增加 provider-neutral
TodoList、公开选择卡和完成后的默认收起行为，并把聊天与运行记录放进同一份可回放合同。

本变更只扩展 0.1 单进程基线，不声称实现持久化恢复型状态机、完整 Approval、RBAC 或
生产级多租户。
