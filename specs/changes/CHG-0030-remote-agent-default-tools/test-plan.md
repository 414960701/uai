---
kind: test-plan
id: CHG-0030-TEST-PLAN
status: complete
---

| 场景 | 证据 |
|---|---|
| 四个 Web 工具注册、manifest 能力和参数 Schema | `backend/tests/test_web_tools.py`、`backend/tests/test_registry.py` |
| 搜索/RSS/Atom/JSON 结果结构化、数量有界、页面正文提取和输出截断 | `backend/tests/test_web_tools.py` 的 MockTransport 测试 |
| 私网/非 HTTPS/敏感 query/危险重定向 fail closed | `backend/tests/test_web_tools.py` |
| 新建 Agent 未提供 tools 时默认挂载，显式空列表保持为空 | `backend/tests/test_api.py` |
| 后端与新建表单预算/默认并发一致 | `backend/tests/test_defaults.py`、`tests/rendered-html.test.mjs` |
| 控制台每个主要导航、Agent 创建向导、工具选择/取消、策略控件和关闭按钮可点击 | `manual-browser-2026-08-02`：独立临时 CDP；含模型配置、Agent revision、Run/Plan/Trace smoke |
| 保存的真实模型连接、真实 Provider Run、calculator、web_fetch 和 web_search 页面调用 | `docs/testing/manual-browser-2026-08-02.md`：同一页面完成连接、创建/发布 Agent 和 4 条成功消息 |
| 回归门禁 | `python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、`npm test`、`make verify`、`git diff --check` |
