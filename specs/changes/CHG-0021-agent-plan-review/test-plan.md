---
kind: test-plan
id: CHG-0021-TEST-PLAN
status: executed
---

- 领域/Runtime：计划 Run 持久化结构化计划；编辑递增版本；批准创建引用相同 plan/version
  和根 revision 的 execute Run；执行成功后回写 completed 与步骤状态。
- API：GET/PATCH plan、approve、reject 的版本冲突和状态边界；批准响应返回新 Run；事件
  history 含 plan.proposed/updated/approved/execution_started/completed。
- 前端：计划卡片显示版本/状态/步骤/风险，修改、批准和拒绝动作接入真实 API；Trace 对
  计划事件使用中文标题且不显示隐藏推理。
- 门禁：`.venv/bin/python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`
  和 `npm test`。
- 浏览器：计划模式生成后停在“待审阅”，批准后跳转到新的执行 Run；窄屏计划卡片和发送
  区不被运行详情覆盖；选择项明确标注为“运行方式（不是模型）”，提交后校验服务端返回
  的 `metrics.execution_mode`，并在聊天区显示“计划模式已选”。2026-08-01 本地浏览器
  smoke：`run_eabd9a9edda745c5` 返回 `execution_mode=plan`、`plan.status=proposed`、
  `tool_calls=0`，聊天区展示“执行计划”卡片。
