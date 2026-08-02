---
kind: test-plan
id: CHG-0036-TEST-PLAN
status: in_progress
target: 0.1
---

| 场景 | 证据 |
|---|---|
| manifest、注册和普通配置 | `backend/tests/test_conversation_tools.py` |
| 当前 Agent 默认 target 与自动新 session | `backend/tests/test_conversation_tools.py::test_conversation_starts_new_session_for_current_agent` |
| 显式 target/revision/mode 和 parent metadata | `backend/tests/test_conversation_tools.py::test_conversation_accepts_explicit_target_and_mode_without_secret_output` |
| 缺失运行端口、非法请求和稳定错误 | `backend/tests/test_conversation_tools.py` |
| Runtime 注入 RunSubmissionPort | `backend/src/uai_forge/run_manager.py`、后端回归门禁 |
| 回归门禁 | `python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、`npm test`、`git diff --check` |
