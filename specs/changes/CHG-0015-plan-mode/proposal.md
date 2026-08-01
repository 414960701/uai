---
kind: change-proposal
id: CHG-0015
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - PLAN-001
  - PLAN-002
  - PLAN-003
---

# Agent 计划模式

在思考偏好之外，Agent 需要一个明确的计划模式，用于先产出可审阅的执行计划而不触发
工具、子 Agent 或外部副作用。计划模式是 Run 级别选择，不修改 Agent revision 或模型
连接配置；用户确认后可以用普通执行模式重新运行。
