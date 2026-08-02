---
kind: test-plan
id: CHG-0033-TEST-PLAN
status: in_progress
target: 0.1
---

| 场景 | 证据 |
|---|---|
| manifest、注册和显式 binding 配置 | `backend/tests/test_workspace_tools.py`、`backend/tests/test_registry.py` |
| root path、越界路径、symlink 和敏感文件 fail closed | `backend/tests/test_workspace_tools.py` |
| 分段读取和有界目录列出 | `backend/tests/test_workspace_tools.py` |
| unified patch 仅允许工作区内、非删除、非二进制目标；无效 patch 结构化拒绝且不写入 | `backend/tests/test_workspace_tools.py`、`backend/tests/test_runtime.py` |
| 固定后端测试命令、Git 状态/差异及结构化结果 | `backend/tests/test_workspace_tools.py`、真实后端 pytest 门禁 |
| Compose workspace mount、非 root 用户和健康检查 | `docker compose config --quiet`、Compose smoke |
| 回归门禁 | `.venv/bin/python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、`npm test`、`git diff --check` |
