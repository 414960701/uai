---
kind: requirements-delta
id: CHG-0036-REQUIREMENTS
status: in_progress
target: 0.1
---

## CONV-001 — 发起下一轮对话

WHEN Agent 显式绑定 `tool.conversation`
THE SYSTEM SHALL 接受有界的 `input`，并允许省略 `agent_id` 以沿用当前 Agent、
省略 `session_id` 以创建新的会话；显式 target SHALL 使用 UAI Forge 已有 Agent/revision 合同。

WHEN 工具发起下一轮
THE SYSTEM SHALL 通过 `RunSubmissionPort` 调用正常 `RunManager.start`，保留 tenant、Agent
revision、session、拓扑、模型配置、工具权限、超时和预算校验；工具不得直接访问 HTTP、SQLite
或供应商对象。

WHEN 下一轮 Run 被接受
THE SYSTEM SHALL 返回新 Run ID、Agent ID/revision、session ID 和 queued/running 状态；失败
SHALL 返回不泄漏内部凭证或堆栈的稳定错误 code。

## CONV-002 — 连续自进化边界

WHEN Agent 把 `tool.conversation` 作为一轮工作的最后一个动作
THE SYSTEM SHALL 允许新 Run 异步提交，使下一轮可以继续检查、研究、修改和测试工作区。

该 change 不把工具加入默认工具集合，也不宣称当前 0.1 已实现 durable Session、跨 Run checkpoint、
全局循环 controller、outbox/idempotency 或生产级调度器。
