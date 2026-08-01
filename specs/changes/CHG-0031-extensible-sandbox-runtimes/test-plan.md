---
kind: test-plan
id: CHG-0031-TEST-PLAN
status: in_progress
---

| 场景 | 证据 |
|---|---|
| sandbox manifest、provider registry 和自有端口 | `backend/tests/test_registry.py`、`backend/tests/test_sandbox.py` |
| Docker argv 无 shell/特权/宿主挂载/网络，且包含资源限制 | `backend/tests/test_sandbox.py::test_docker_sandbox_command_is_hardened_and_argv_only` |
| command NUL/空值、provider 配置边界 fail closed | `backend/tests/test_sandbox.py`、registry schema validation |
| sandbox tool 只接受 argv 并显式配置 provider | `backend/tests/test_sandbox.py`、`backend/tests/test_tool_argument_validation.py` |
| 真 Docker 子容器、rootless、runsc/Kata runtime 和超时清理 | 部署环境可用时运行，当前仍是 acceptance 待补证据 |
| 回归门禁 | `python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、`npm test`、`git diff --check` |
