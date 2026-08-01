---
kind: requirements-delta
id: CHG-0022-REQUIREMENTS
status: accepted
target: 0.1
---

# Requirements delta

## TASK-001 — 复杂任务自动 TodoList

WHEN an execute-mode Run is judged to be multi-step by the provider-neutral complexity heuristic
THE SYSTEM SHALL persist a `TaskTodoList` with ordered public `TodoItem` records, status and
timestamps, and SHALL NOT create a duplicate automatic TodoList for an explicit plan Run.

## TASK-002 — Todo lifecycle and observability

THE SYSTEM SHALL expose Todo creation, update and terminal events in the ordered Run history;
the chat and Run History surfaces SHALL render the same Todo state without exposing hidden
chain-of-thought, credentials or raw tool arguments.

## TASK-003 — Structured choice interaction

WHEN a model returns the bounded provider-neutral choice marker, THE SYSTEM SHALL validate and
persist a `ChoicePrompt`, remove the marker from public prose, and provide explicit Continue and
Skip actions. Unknown options, invalid selection cardinality and sensitive text SHALL fail closed.

## TASK-004 — Public reasoning defaults

WHEN a Run reaches a terminal state, the public reasoning panel SHALL default to collapsed while
remaining manually expandable; it SHALL show only public stage summaries and not hidden reasoning.
