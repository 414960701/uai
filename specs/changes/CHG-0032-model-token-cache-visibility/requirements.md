---
kind: requirements-delta
id: CHG-0032-REQUIREMENTS
status: accepted
target: 0.1
---

## OBS-011 — Provider-neutral cache token usage

WHEN a model Provider reports input tokens served from a cache
THE SYSTEM SHALL map them to the UAI Forge `TokenUsage.cached_input_tokens` field, without
exposing provider-specific response objects or field names in the core contract.

WHEN a Provider reports input tokens written to a cache
THE SYSTEM SHALL map them to the optional `TokenUsage.cache_creation_input_tokens` field.
Cache-read and cache-creation counters SHALL remain metadata about `input_tokens`; they SHALL
NOT be added a second time to `total_tokens` when the provider's input count already includes
them.

WHEN streaming usage arrives in multiple chunks
THE SYSTEM SHALL preserve the latest non-missing value for each usage dimension and publish the
complete cache counters in the corresponding `model.completed` event. Providers that do not
report a cache counter SHALL use an explicitly unknown value rather than claiming a zero hit.

## UI-011 — Per-call cache visibility

WHEN a Run contains a completed model invocation
THE SYSTEM SHALL show, for that invocation, input tokens, output tokens, and cache-hit input
tokens in the Trace/event detail and public execution summary. Cache-creation input tokens SHALL
be shown when reported.

Historical events without the new fields SHALL remain renderable and show cache status as
“未报告”; the UI SHALL NOT display complete prompts, credentials, hidden reasoning, or raw
provider response objects.
