---
kind: test-plan
id: CHG-0031-TEST-PLAN
status: complete
---

- 模型/API：创建草稿、发布草稿、回滚 latest、回滚后继续保存新 revision，过期 CAS
  不写入；版本历史返回状态和 latest 标签。
- Runtime：latest、显式 draft、显式 published revision 都能解析为实际 AgentSpec；
  child mount 留空跟随 latest，显式值固定对应 revision。
- Frontend：源码合同验证编辑器包含草稿/发布/历史/回滚动作，RunModal 和 mount 选择器
  展示状态化版本；不存在 Instance 导航或旧 Run 字段。
- 门禁：`.venv/bin/python -m pytest backend/tests -q`、`npm run lint`、
  `npm run typecheck`、`npm test`、`git diff --check`。
