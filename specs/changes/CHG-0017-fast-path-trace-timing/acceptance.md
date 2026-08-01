---
kind: acceptance
id: CHG-0017-ACCEPTANCE
status: passed
---

- [x] 缺少城市的天气消息不再触发父/子/父模型链路。
- [x] Trace 显示总耗时、模型/工具/委派/Agent 阶段耗时和运行中 elapsed。
- [x] 所有新增事件字段通过安全断言，不包含凭证、prompt 或隐藏思维。
- [x] 后端/前端门禁和容器 smoke 通过。

验收证据（2026-08-01）：`run_208b9adc88ae49b6` 的天气澄清 Run 端到端约 85 ms、运行时
`elapsed_ms=10.5`，事件中没有 `model.*`、`tool.*` 或 `delegation.*`；运行记录页显示 12 ms、
8 条事件、0 次模型调用。浏览器流式 smoke `run_34be4d6ae38144a7` 显示实时公开阶段和增长中的
elapsed，取消后公开卡片显示“已取消”。
