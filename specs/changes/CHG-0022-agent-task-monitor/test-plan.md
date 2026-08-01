---
kind: test-plan
id: CHG-0022-TEST-PLAN
status: in_progress
---

- 领域：复杂度启发式、Todo 状态转换、Choice marker 安全解析和敏感文本拒绝。
- API/Run：复杂 execute Run 返回并持久化 Todo，事件历史包含 created/updated/completed。
- 前端：类型检查、Lint、渲染测试；浏览器验证终态 reasoning 收起、Todo 展示和浅色主题。
- 门禁：`.venv/bin/python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`
  和 `npm test`。
