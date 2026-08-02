---
kind: acceptance
id: CHG-0035-ACCEPTANCE
status: pending
---

- [ ] `tool.git` 显式绑定后可完成 status、diff、常规 pull、commit、push 和 commit/push。
- [ ] 工具不接受任意命令或模型可控 flags、force/delete/tag；detached repository 有结构化失败证据。
- [ ] `credential_ref` 只经内部 resolver 使用；真实 Token 不进入仓库、prompt、事件、日志或测试。
- [ ] 发现硬编码 credential-like 内容时拒绝提交并清理暂存区；该检查不引入人工审批流程。
- [ ] 提交失败和 push 失败均有可恢复结构化结果；push 失败保留 commit SHA。
- [ ] 新 Agent 默认不挂载 Git；Compose 和完整后端/前端验证通过。
