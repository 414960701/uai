---
kind: test-plan
id: CHG-0024-TEST-PLAN
status: in_progress
---

- 前端：`npm run lint`、`npm run typecheck`、`npm test`。
- 后端：复杂度判断、动作化 Todo 标题、终态 Todo 生命周期和 Plan 不重复清单测试。
- 浏览器：桌面和窄屏截图；空对话不自动展开 Trace；运行中 Task Monitor 出现；终态
  思考摘要收起；选择卡可选、跳过和继续；聊天历史仍是唯一主滚动容器。
- 安全：任务监视器不回显原始输入、凭证、原始 reasoning 或未脱敏工具参数。
