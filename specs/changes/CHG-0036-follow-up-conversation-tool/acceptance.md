---
kind: acceptance
id: CHG-0036-ACCEPTANCE
status: pending
---

- [ ] Agent 显式挂载 `tool.conversation` 后能创建下一轮 queued Run 并返回真实 Run ID。
- [ ] 下一轮复用正常 RunManager 合同，事件流和控制面可继续观测。
- [ ] 默认新建 Agent 不自动挂载该工具。
- [ ] 缺失端口、无效请求、未知 Agent 和 active-session 冲突均有稳定失败证据。
- [ ] 完整后端/前端/Compose 验证通过。
