---
kind: test-plan
id: CHG-0025-TEST-PLAN
status: in_progress
---

- 前端：`npm run lint`、`npm run typecheck`、`npm test`、`git diff --check`。
- 浏览器：聊天页与控制台桌面/窄屏截图；确认侧栏、顶部栏、面板、输入框、按钮、运行
  记录、拓扑、弹层均为浅色层级；确认聊天历史仍是唯一内部滚动容器。
- 可访问性：确认正文、辅助文字、主按钮和 focus ring 在浅色背景上可辨识；状态颜色
  仍由文字/图标/徽章语义共同表达。
- 回归：确认流式输出、Plan、Todo、Choice、Trace、Enter 换行与 Ctrl/⌘+Enter 发送不受影响。
