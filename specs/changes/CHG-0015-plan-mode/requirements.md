---
kind: requirements-delta
id: CHG-0015-REQUIREMENTS
status: proposed
target: 0.1
---

# Requirements delta

## PLAN-001 — Run 计划模式合同

THE SYSTEM SHALL define `execution_mode` as `execute` or `plan`, defaulting to `execute`.
The Run request, persisted Run metrics, and provider-neutral `ModelRequest` SHALL carry the
selected value.

## PLAN-002 — 计划模式安全边界

WHEN `execution_mode=plan`
THE SYSTEM SHALL not expose configured tools or mounted child-agent definitions to the model,
shall not invoke tools or delegate children, and shall preserve the normal Run/Event/Trace
sequence for the visible planning response.

The public event stream SHALL identify plan mode and state that the result is a plan only. A
provider or custom adapter returning unexpected tool calls in plan mode SHALL be fail-closed and
must not execute the call.

## PLAN-003 — 前端选择与可审阅结果

THE SYSTEM SHALL expose `执行` and `计划模式` in Agent 对话 and the standalone Run launcher.
The selected mode SHALL be visible before submission and in Run details. Plan mode SHALL state
that it produces a reviewable plan without executing tools or hidden chain-of-thought.
