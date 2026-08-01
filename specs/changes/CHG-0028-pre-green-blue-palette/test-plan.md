---
kind: test-plan
id: CHG-0028-TEST-PLAN
status: in_progress
---

- 前端：`npm run lint`、`npm run typecheck`、`npm test`、`git diff --check`。
- 后端：`.venv/bin/python -m pytest backend/tests -q`，确认展示层变更没有破坏运行合同。
- 浏览器：重建 Docker 后读取实际 computed colors；确认主按钮/选中态为 `#5667d8`，公开
  进行中阶段为 `#4c82c9`，成功/完成状态仍为绿色，聊天历史内部滚动且发送按钮可见。
- 回归：确认 Enter 换行、Ctrl/⌘+Enter 发送、流式事件、Plan、Todo、Choice、Trace 和
  IME 组合输入规则不变。
