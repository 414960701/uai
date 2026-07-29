# UAI Forge agent instructions

本项目采用规范驱动开发。任何较大变更先阅读：

1. `docs/governance/constitution.md`
2. 对应的 `specs/current/*/spec.md`
3. 相关 `docs/architecture/adr/*`
4. `specs/traceability.yaml`

必须遵守：

- 不把 AgentScope、LangGraph、AutoGen 或任一提供商的对象泄漏到核心契约。
- 扩展点先更新 manifest/协议与兼容测试，再实现适配器。
- Agent 挂载变更必须验证静态环、动态深度、预算、并发、超时和取消传播。
- 密钥只保存引用；不得写入配置、事件、日志、测试快照或前端示例。
- 已接受 ADR 不原地改写；用新的 ADR supersede。
- 需求偏离时先提交 spec delta，禁止让代码静默改变规范。
- 后端变更运行 `python -m pytest backend/tests -q`。
- 前端变更运行 `npm run lint && npm run typecheck && npm test`。
- 新需求必须在 `specs/traceability.yaml` 连接实现和测试证据。

当前 `0.1.0` 是单进程基线。不得声称已具备分布式恢复、完整 RBAC、插件沙箱或
生产级多租户，除非相应规范、实现和故障测试同时完成。
