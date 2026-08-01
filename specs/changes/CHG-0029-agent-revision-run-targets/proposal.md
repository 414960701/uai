---
kind: change-proposal
id: CHG-0029
status: in_progress
target: 0.1
date: 2026-08-02
implementation_status: in_progress
requirements:
  - RUN-010
  - UI-006
---

# Agent revision 直接运行

当前控制台把运行目标拆成 Agent 和运行实例。Instance 在单进程基线中只重复保存
Agent revision，并增加当前尚未接入部署的 environment、启停和容量字段。它增加了
首用成本，却没有提供当前运行时真正需要的能力。

本变更将运行目标统一为 Agent，并在发起运行时提供可选的 revision 选择：不选时使用
提交时的最新 revision，选择时使用对应不可变历史 revision。移除新的 Instance 管理、
API 和运行时上下文；旧数据库记录只保留读取兼容，不再产生新的 Instance 数据。
