---
kind: requirements-delta
id: CHG-0017-REQUIREMENTS
status: implemented
target: 0.1
---

# Requirements delta

## PERF-001 — 声明式快速澄清路径

WHEN root Agent declares the non-secret label `routing.fast_path=weather_missing_location`
AND the input expresses a weather intent without a detectable city, region, or country
THE SYSTEM SHALL complete a bounded clarification response without a model, tool, or child-Agent
call. The Run SHALL still publish the normal lifecycle, public progress, terminal output, metrics,
and ordered event history so the shortcut is observable and replayable.

WHEN the same Agent input contains a location, or the label is absent or unknown
THE SYSTEM SHALL keep the existing model/tool/delegation execution path.

The shortcut SHALL use a fixed safe response and SHALL NOT inspect credentials, prompts, provider
objects, or hidden reasoning content. It SHALL be opt-in; arbitrary Agent labels SHALL NOT execute
as code or change permissions.

## PERF-002 — 阶段完成耗时

WHEN a model, tool, delegation, or Agent operation completes or fails
THE SYSTEM SHALL include a non-negative `duration_ms` in the corresponding completion/failure
event payload. The value SHALL measure only the operation represented by that event and SHALL NOT
include secrets, prompt text, or provider response bodies.

## TRACE-001 — 可观测耗时投影

WHEN a Run has timed events
THE SYSTEM SHALL show total duration, per-stage duration, active-stage elapsed time, and the
existing trace/span/parent relationship in the Run inspector and Run history Trace. The UI SHALL
derive these values from the ordered event stream, show Chinese human-readable labels plus stable
IDs, and retain the existing public-summary boundary for hidden reasoning and sensitive fields.
