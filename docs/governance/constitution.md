---
kind: normative
id: GOV-CONSTITUTION
status: approved
version: 1.0.0
last_reviewed: 2026-07-30
---

# 项目宪章

1. **协议先行**：公共行为先有 Pydantic/JSON Schema/OpenAPI/Event 合同，再有适配器。
2. **内核独立**：核心域不得暴露 AgentScope、LangGraph、厂商 SDK 或 Web 框架类型。
3. **可恢复优先**：跨外部边界的动作必须可记录、可取消；完整版本必须 checkpoint。
4. **默认最小权限**：子 Agent 有效权限不能大于父权限、mount scope 和子策略交集。
5. **密钥只存引用**：密钥不进入配置查询、事件、日志、prompt、Trace 或前端持久化。
6. **扩展 fail closed**：安全、权限、协议和能力不兼容时拒绝启用；观测扩展可降级。
7. **预算覆盖调用树**：模型、工具和子 Agent 消耗同一根预算账本。
8. **不虚假承诺**：at-least-once 不称 exactly-once；单进程不称分布式；示例 header
   不称认证。
9. **规范可追踪**：每条 SHALL 连接任务、代码与自动化测试。
10. **证据优于自报**：AI 或开发者说“已完成”不算证据，门禁命令和可复现实验才算。

变更宪章需要新 ADR、迁移影响和全体当前规范一致性检查。
