---
kind: change-proposal
id: CHG-0021
status: in_progress
target: 0.1
date: 2026-08-01
implementation_status: in_progress
supersedes:
  - CHG-0015 PLAN-003 的仅选择器式计划结果
requirements:
  - PLAN-004
  - PLAN-005
  - PLAN-006
  - PLAN-007
  - PLAN-008
---

# Agent 计划审阅闭环

当前计划模式虽然阻止了工具和子 Agent，但用户看到的只是一次普通 Run 和一条提示，无法
确认计划版本、修改内容，也无法在批准后无歧义地进入执行。该变更把计划变成公开、结构化、
可持久回放的 Run 产物，形成“生成 → 审阅/修改 → 批准或拒绝 → 执行 → 回写状态”的闭环。

本变更只扩展 0.1 单进程能力。它不声称实现 foundation 中尚未完成的分布式 Approval、
CAS Run 状态机、checkpoint、outbox、RBAC 或多租户身份授权。
