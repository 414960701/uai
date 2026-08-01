---
kind: requirements-delta
id: CHG-0014-REQUIREMENTS
status: proposed
target: 0.1
---

# Requirements delta

## THINK-001 — 受治理的思考偏好

THE SYSTEM SHALL define `thinking_mode` as one of `off`, `auto`, or `on`, defaulting to
`auto` for backward compatibility. The Run request, persisted Run metrics, and provider-neutral
`ModelRequest` SHALL carry the same value.

思考模式 SHALL be a request preference only; it SHALL NOT be interpreted as permission to store
or display raw reasoning, thinking tokens, complete prompts, credentials, or provider objects.

## THINK-002 — Provider 方言映射

WHEN a Provider supports a declared thinking protocol
THE SYSTEM SHALL map `on/off` to that protocol while leaving `auto` unspecified so the model
keeps its native default. The initial adapters MAY support:

- OpenAI-compatible `reasoning_effort` (`high` / `none`);
- Qwen-compatible `enable_thinking` (`true` / `false`);
- Anthropic extended thinking with a bounded non-secret `budget_tokens` value;
- native reasoning models whose model ID already selects thinking, with no extra request field.

WHEN the provider/model does not declare a recognized protocol
THE SYSTEM SHALL keep the request valid, preserve the selected preference in Run observability,
and expose a public degraded/compatibility notice instead of guessing an unsafe payload.

## THINK-003 — 前端选择与观测

THE SYSTEM SHALL expose a Chinese `思考模式` selector in Agent 对话 and the standalone Run
launcher with `关闭`、`自动`、`开启` options. The current selection SHALL be visible before
submission and in Run/Trace metadata after submission.

The UI SHALL clearly state that enabling thinking does not reveal hidden chain-of-thought; only
public execution phases and final visible output are shown.
