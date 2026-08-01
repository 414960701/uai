---
kind: test-plan
id: CHG-0027-TEST-PLAN
status: in_progress
---

- 前端：`npm run lint`、`npm run typecheck`、`npm test`、`git diff --check`。
- 后端回归：`.venv/bin/python -m pytest backend/tests -q`，确认 Plan、Todo、Choice 合同
  和安全边界未被展示层改动破坏。
- 浏览器桌面：普通回答不显示 Task Monitor；复杂 execute Run 显示 Todo/Artifacts/
  Skills & MCP；终态思考默认收起且可展开；Composer 默认执行模式，Plan 需主动选择。
- 浏览器交互：Choice 单选/多选、推荐、必选/可跳过、Skip/Continue；Plan 继续规划、
  修改、批准并执行；Trace 仍是二级详情。
- 浏览器窄屏：只有聊天历史内部滚动，Composer 可见且发送按钮可点击，任务/Trace 不
  覆盖输入区。
