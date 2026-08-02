---
kind: test-plan
id: CHG-0038-TEST-PLAN
status: in_progress
target: 0.1
---

| 场景 | 证据 |
|---|---|
| 单个大工具结果被截断并保留恢复提示 | `backend/tests/test_runtime.py::test_large_tool_results_are_bounded_before_the_next_model_call` |
| 旧工具轮次按完整 assistant/tool 对压缩 | `backend/tests/test_runtime.py::test_model_history_compaction_keeps_base_and_recent_tool_rounds` |
| 当前任务保留、旧 memory 可丢弃 | `backend/tests/test_runtime.py::test_model_history_compaction_preserves_current_task_over_old_memory` |
| 相同工具请求可识别且告警不保留原始参数 | `backend/tests/test_runtime.py::test_tool_call_signature_is_stable_without_retaining_arguments`、`backend/tests/test_runtime.py::test_repeated_tool_call_emits_non_blocking_feedback` |
| 委派结果走同一有界序列化路径 | `backend/src/uai_forge/runtime.py::_delegate`、后端回归门禁 |
| 研究证据格式和公开来源边界 | `docs/research/README.md`、`specs/traceability.yaml` |
| 回归门禁 | `python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、`npm test`、`docker compose config --quiet`、`git diff --check` |
