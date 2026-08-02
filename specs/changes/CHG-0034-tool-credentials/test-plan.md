---
kind: test-plan
id: CHG-0034-TEST-PLAN
status: complete
target: 0.1
---

| 场景 | 证据 |
|---|---|
| 新建/列表/更新/清除/停用工具凭证 | `backend/tests/test_tool_credentials.py` |
| 密文存储、掩码响应、tenant 隔离、验证错误不回显输入 | `backend/tests/test_tool_credentials.py` |
| 版本 CAS、引用 Agent revision 时删除失败 | `backend/tests/test_tool_credentials.py` |
| v3 数据库无损增加 v4 工具凭证表 | `backend/tests/test_tool_credentials.py` |
| 控制台导航、页面和不回显 token 的数据流 | `tests/rendered-html.test.mjs`、`npm run lint`、`npm run typecheck` |
| 回归门禁 | `python -m pytest backend/tests -q`、`npm test`、`docker compose config --quiet`、`git diff --check` |
