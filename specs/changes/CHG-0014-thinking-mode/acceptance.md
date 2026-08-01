---
kind: acceptance
id: CHG-0014-ACCEPTANCE
status: passed
---

- [x] Run、ModelRequest、Runtime 和 Provider 共享 `off/auto/on` 合同。
- [x] OpenAI-compatible、Qwen-compatible、Anthropic 和未知方言行为有测试证据。
- [x] Agent 对话与发起运行入口可选择并显示思考模式。
- [x] Trace 记录模式但不保存或展示原始 reasoning/thinking 内容。
- [x] 后端与前端门禁通过，真实浏览器 smoke 验证选择器和降级提示。

验收证据（2026-08-01）：`backend/tests` 122 项通过；`npm run lint`、
`npm run typecheck`、`npm test` 通过。浏览器 smoke 在 Agent 对话和独立 Run 面板确认了
“思考模式”选择器、中文选项和“不展示原始思考内容”提示；Provider 测试覆盖
OpenAI reasoning effort、Qwen enable_thinking、Anthropic extended thinking 与未知方言
兼容降级。
