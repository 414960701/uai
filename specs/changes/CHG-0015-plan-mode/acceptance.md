---
kind: acceptance
id: CHG-0015-ACCEPTANCE
status: passed
---

- [x] `execution_mode=plan` 在 Run/ModelRequest/Runtime 中有统一合同。
- [x] 计划模式不暴露或执行工具、委派和外部副作用。
- [x] Agent 对话与发起运行入口可以选择并显示计划模式。
- [x] Trace 保留模式与公开阶段，不保存隐藏思维原文。
- [x] 后端/前端门禁与真实浏览器 smoke 通过。

验收证据（2026-08-01）：真实 Run `run_f71b976871044b69` 使用 `execution_mode=plan`
成功完成，产生 1267 条有序事件，其中 1255 条 `model.delta`、0 条工具事件、0 条委派
事件；`run.started`、`model.started` 和 Run metrics 均记录 `plan`，公开阶段显示“计划
模式：只生成计划，不调用工具或子 Agent”。浏览器同时确认 Agent 对话和独立 Run 面板
的计划模式选择器与保护提示。`backend/tests` 122 项、前端 typecheck/lint/test 全部通过。
