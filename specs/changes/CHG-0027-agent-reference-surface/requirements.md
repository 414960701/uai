---
kind: requirements-delta
id: CHG-0027-REQUIREMENTS
status: proposed
target: 0.1
---

## CHAT-027 — Conversation-first surface

WHEN the Agent conversation is open
THE SYSTEM SHALL make the transcript and composer the primary continuous reading surface,
shall keep users' messages lightweight, and shall not present routine replies as nested admin
cards.

## CHAT-028 — Public activity and terminal collapse

WHEN a Run is active
THE SYSTEM SHALL show one compact public activity line with a live status and shall keep the
full ordered public stage list available on demand.

WHEN a Run reaches a terminal state
THE SYSTEM SHALL collapse the public stage list by default, preserve a one-line summary, and
allow manual expansion without exposing hidden chain-of-thought.

## CHAT-029 — Explicit mode boundary

WHEN a user sends a message
THE SYSTEM SHALL use execute mode by default; complexity MAY create an automatic TodoList, but
complexity SHALL NOT silently switch the Composer into Plan mode.

WHEN the user explicitly selects Plan
THE SYSTEM SHALL show an unambiguous review state and SHALL create no automatic TodoList for
that Plan Run.

## CHAT-030 — Complexity-aware task rail

WHEN an execute-mode Run has a persisted automatic TodoList
THE SYSTEM SHALL show a compact Task Monitor with ordered Todos, progress, artifacts and public
capabilities; simple execute Runs SHALL keep that rail out of the primary workspace.

## CHAT-031 — Choice as an actionable card

WHEN a validated ChoicePrompt is open
THE SYSTEM SHALL clearly expose single/multiple semantics, required or skippable state,
recommended options, selected state, Skip and Continue actions, and SHALL keep the ordinary
Composer usable.
