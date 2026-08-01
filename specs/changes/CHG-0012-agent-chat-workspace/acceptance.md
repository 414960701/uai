---
kind: acceptance
id: CHG-0012-ACCEPTANCE
status: accepted
---

# Acceptance

- [x] Agent 对话作为独立导航和工作区可打开。
- [x] 会话侧栏按现有 `session_id` 聚合，并能从 URL 恢复当前运行。
- [x] 发送、运行中、成功、失败、取消、重试和 SSE 详情均由现有 Run/SSE 事实驱动。
- [x] 工具、扩展、记忆和中间件以中文名/描述为主，英文稳定 ID 可见。
- [x] 键盘、窄屏、aria 状态和 reduced-motion 处理通过前端门禁。
- [x] 未新增 Session/聊天后端事实源，且密钥不进入 UI 持久化或事件。

验收证据（2026-08-01）：四项项目门禁通过；真实控制面 Run
`run_3c40135b389c4431` 验证成功终态，`run_0f5f1ac77a7147ce` 验证工具事件中文名与
`tool.echo` ID，`run_daaed288efd84181` 验证取消，`run_9b665ee56772478a` 与其重试
`run_79842e3af93941a5` 验证失败/重试；浏览器 smoke 覆盖 URL 恢复、390×844 窄屏、焦点、
折叠详情、扩展中心中文文案和控制台无 error。
