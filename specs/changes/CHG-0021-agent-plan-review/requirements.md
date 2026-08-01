---
kind: requirements-delta
id: CHG-0021-REQUIREMENTS
status: accepted
target: 0.1
---

# Requirements delta

## PLAN-004 — 结构化计划产物

WHEN a Run uses `execution_mode=plan` and completes successfully
THE SYSTEM SHALL persist a provider-neutral `ExecutionPlan` containing `plan_id`, `run_id`,
`session_id`, `version`, `title`, `goal`, `assumptions`, ordered `steps`, `risks`, `status`,
and timestamps.

The plan SHALL be a public execution summary and SHALL NOT contain hidden chain-of-thought,
provider objects, credentials, or raw tool arguments.

## PLAN-005 — 版本化人工审阅

WHEN a plan is `proposed` or `needs_revision`
THE SYSTEM SHALL allow a user to edit it with an expected version, reject it, or approve it.
An edit SHALL increment the version and return the plan to `needs_revision`; a stale version
SHALL fail closed with a conflict.

## PLAN-006 — 批准后执行

WHEN a user approves a plan version
THE SYSTEM SHALL create a separate execute Run referencing the plan ID, source plan Run ID,
and approved version, while preserving the source Run's root Agent revision and Instance target.
The plan Run SHALL remain review history; plan mode SHALL never execute the approved work itself.

## PLAN-007 — 计划状态与全链路可观测

THE SYSTEM SHALL expose plan lifecycle events in the ordered Run Event history, including
proposed, updated, approved, execution started, completed, failed, rejected, and cancelled
outcomes where applicable. Chat and Run History SHALL render the same plan artifact and its
current version/status.

## PLAN-008 — 安全边界与明确动作

WHEN planning is active
THE SYSTEM SHALL hide configured tools and mounted child agents from the model, fail closed on
unexpected tool calls, and state that external side effects do not run. The UI SHALL provide
explicit “修改计划”, “批准并执行”, and “暂不执行” actions instead of implying that selecting
the mode has already started execution.
