---
kind: requirements-delta
id: CHG-0016-REQUIREMENTS
status: accepted
target: 0.1
---

# Requirements delta

## THINK-004 — 公开思考过程

WHEN a Run has public progress, model, tool, or delegation events
THE SYSTEM SHALL present a user-facing `思考过程` summary with ordered public stages, current
status, and safe non-sensitive detail in Agent 对话、Run inspector, or Trace.

The summary SHALL be derived from the existing Run Event stream and SHALL NOT create a second
reasoning fact source.

## THINK-005 — 隐藏推理隔离

The public summary SHALL not display or persist raw chain-of-thought, reasoning tokens, complete
prompts, credentials, provider objects, or unredacted tool arguments. It SHALL label the view as a
public summary and preserve the existing final-output and Trace disclosure boundary.
