---
kind: adr
id: ADR-0002
status: accepted
date: 2026-07-30
---

# ADR-0002：分离版本化定义、实例、会话与 Run

## 背景

可复用 Agent 配置、部署容量、对话状态和一次执行有不同生命周期。混成一个可变 Agent
对象会让审计、恢复、扩缩容和回滚无法确定。

## 决定

- Agent Definition 有稳定 ID；Revision 是不可变配置快照。
- Agent Instance 引用一个 Definition/Revision，并承载环境和容量。
- Session 保存会话、权限上下文和 peer inbox，不保存定义身份。
- Run 固定引用实际执行的 Agent Revision、插件和策略版本。
- Invocation/Checkpoint 是 Run 内可恢复边界。

`0.1.0` 的 `AgentSpec`、`AgentInstance`、`RunRecord` 是这一决定的部分实现；Session、
Invocation、Checkpoint 仍待实现。

## 结果

- 可以回放“当时实际运行了什么”。
- Instance 可独立升级或回滚 Revision。
- Session 和 durable peer 可跨 Run 持续。
- 需要迁移当前 `AgentSpec` 组合模型，并保持既有 ID/revision 查询兼容。
