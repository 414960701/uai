---
kind: requirements-delta
id: CHG-0024-REQUIREMENTS
status: proposed
target: 0.1
---

## CHAT-020 — Chat-first hierarchy

WHEN the Agent conversation is open
THE SYSTEM SHALL make the transcript and composer the primary surface, SHALL NOT open the
full Run inspector automatically, and SHALL preserve an explicit action to open Trace details.

## CHAT-021 — Terminal reasoning collapse

WHEN a Run reaches a terminal state
THE SYSTEM SHALL collapse its public reasoning summary automatically, SHALL keep a one-line
status summary visible, and SHALL allow manual expansion without exposing hidden chain-of-thought.

## CHAT-022 — Complexity-aware task monitor

WHEN an execute-mode Run is classified as multi-step
THE SYSTEM SHALL show a task monitor with ordered Todos, progress, artifacts and public
capabilities; simple questions SHALL keep the monitor out of the primary chat path. Plan Runs
SHALL show plan progress instead of creating a duplicate automatic TodoList.

## CHAT-023 — Choice interaction hierarchy

WHEN a Run is waiting for a bounded user choice
THE SYSTEM SHALL render a focused selection card with clear single/multiple semantics, required
state, recommended option, Skip and Continue actions, and SHALL keep the normal composer usable.

## CHAT-024 — Trace separation

WHEN a user opens Run details
THE SYSTEM SHALL expose the existing ordered event and trace data in the inspector, while the
chat surface SHALL show only safe public summaries and not raw event payloads, credentials or
unredacted tool arguments.
