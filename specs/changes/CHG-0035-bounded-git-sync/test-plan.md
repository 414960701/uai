---
kind: test-plan
id: CHG-0035-TEST-PLAN
status: in_progress
target: 0.1
---

| 场景 | 证据 |
|---|---|
| manifest、注册和非默认挂载 | `backend/tests/test_git_tools.py`、`backend/tests/test_registry.py`、`tests/rendered-html.test.mjs` |
| repository/remote/branch 读取、detached 边界和常规工作区状态 | `backend/tests/test_git_tools.py` |
| 常规 pull、当前 branch push、禁止 force/delete/tag | `backend/tests/test_git_tools.py` |
| `git add --all`、commit、commit/push、credential-like 内容拦截和 push 失败可恢复 | `backend/tests/test_git_tools.py` |
| credential_ref 私有 resolver 和结果不泄漏 | `backend/tests/test_git_tools.py`、`backend/tests/test_tool_credentials.py` |
| Agent Runtime 私有 credential port 上下文 | `backend/tests/test_git_tools.py`、后端集成回归 |
| 回归门禁 | `python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、`npm test`、`docker compose config --quiet`、`git diff --check` |
