---
kind: test-plan
id: CHG-0018-TEST-PLAN
status: executed
---

- 前端静态门禁：渲染产物继续包含 Agent 对话、公开摘要和安全边界；正文投影与活动条实现
  通过渲染源码断言。
- 前端质量：运行 `npm run lint`、`npm run typecheck` 和 `npm test`。
- 浏览器 smoke：成功、流式、取消和失败消息均保持单一阅读方向；加粗、列表和行内代码
  可读；思考过程可折叠；侧栏、顶部栏、运行记录和配置页保持统一浅色表面；控制台无错误。
- 安全回归：源码不引入 `dangerouslySetInnerHTML`，正文投影不读取或持久化凭证和隐藏思维。
