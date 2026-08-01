---
kind: acceptance
id: CHG-0016-ACCEPTANCE
status: passed
---

- [x] Agent 对话中可展开查看“思考过程（公开摘要）”。
- [x] Run inspector 和运行记录 Trace 显示相同的公开阶段顺序。
- [x] 流式运行过程中公开摘要随阶段事件更新，完成后保留历史摘要。
- [x] 原始 reasoning、prompt、凭证和未脱敏工具参数不进入摘要。
- [x] 后端/前端门禁和浏览器 smoke 通过。

验收证据（2026-08-01）：浏览器 smoke 在聊天、Run inspector 和运行记录 Trace 中确认了
同一组公开阶段“准备上下文 → 模型分析 → 分析任务”；流式阶段随 SSE 事件更新，Trace
保留顺序和时间。`backend/tests` 124 项通过；`npm run typecheck`、`npm run lint`、
`npm test` 通过；前端源断言确认摘要忽略 `model.delta`，并明确不显示隐藏思维原文。
