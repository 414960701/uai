---
kind: acceptance
id: CHG-0019-ACCEPTANCE
status: in_progress
---

- [x] 带工具的真实 Agent Run 在最终回复阶段产生多个 `model.delta`；`run_84e8f48a31e047d8`
  在终态前产生 4 条增量。
- [x] OpenAI-compatible / Anthropic stream 工具片段通过 Provider-neutral 合同聚合，工具
  参数不进入正文事件。
- [x] 聊天 compact 公开进度默认显示单行实时活动，展开后可查看阶段轨迹；完整 Trace
  继续可审阅。
- [x] 隐藏 reasoning、prompt、凭证和未脱敏工具参数保持隔离。
- [ ] Docker 重建后的浏览器视觉 smoke 通过，控制台无新增错误（服务已健康，待附着 Chrome
  页面完成交互检查）。
