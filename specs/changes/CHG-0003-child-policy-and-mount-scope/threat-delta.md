---
kind: threat-delta
id: CHG-0003-THREAT
status: accepted
---

# Threat delta

| 威胁 | 处置 |
|---|---|
| 宽根预算掩盖 child 本地 tool/token 上限 | 每 invocation 本地 ledger 与根 ledger 双扣减 |
| child 慢调用占住根容量 | child timeout 包含许可等待和执行，取消时释放 lease/semaphore |
| child 并行 fan-out 绕过本地上限 | 根、父 invocation、mount 三层 semaphore 同时准入 |
| child 以宽 root depth 绕过本地深度 | 传播 ancestor 绝对上限并与 child 本地相对上限取较小值 |
| 下游 mount 恢复上游已撤销工具 | 插件 ID scope 沿树取交集；`null` 只继承 |
| provider 伪造未暴露工具调用 | definition 过滤 + 执行前二次 scope 检查 |
| mount allowlist 把 child `deny` 升级为允许 | scope 检查后仍执行 ToolBinding permission |
| 空/缺失字段语义混淆 | `null`=无新增限制，`[]`=拒绝全部，写入合同与回归测试 |
