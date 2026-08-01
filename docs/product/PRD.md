---
kind: normative
id: PRD-UAI-FORGE
status: approved
version: 0.1.0
last_reviewed: 2026-07-31
---

# UAI Forge 产品需求

## 问题

开发者需要在不绑定单一模型厂商或编排框架的前提下，配置多个 Agent、把 Agent
挂载为可调用子 Agent、运行团队并解释每次模型/工具/委派行为。常见开源框架在
“写出 demo”上很强，但版本治理、扩展兼容、预算、权限、后台和本地/云一致性分散。

## 目标

- `OBJ-001`：一套 Python 3 运行时支持单 Agent 和多 Agent 协作。
- `OBJ-002`：Web 后台可管理 Agent 定义、修订、挂载、运行和扩展。
- `OBJ-003`：稳定内核不绑定任何一个开源框架或模型提供商。
- `OBJ-004`：本地和云端使用相同领域合同，仅替换部署适配器。
- `OBJ-005`：需求、设计、实现和测试可追踪，减少 AI 开发漂移。

## 用户

- 平台开发者：编写 Provider、Tool、Memory 或基础设施适配器。
- Agent 构建者：配置提示词、模型、工具、子 Agent 与策略。
- 运行人员：选择 Agent revision、发起/取消运行、查看调用链和预算。
- 安全/审计人员：验证权限、版本、事件、租户和密钥边界。

## MVP 能力

1. Agent 定义以版本化修订保存，更新使用乐观并发。
2. 发起 Run 时可选择 Agent 的历史 revision；未选择时使用提交时 Agent 的 latest 标签。
3. 父 Agent 可按 alias 挂载多个子 Agent，并可让挂载留空以跟随子 Agent latest，或显式
   固定历史 revision。
4. 子调用受到深度、总 step、总 tool call、token、超时和并发限制。
5. 挂载图有缺失节点、禁用节点、版本钉住和循环检查。
6. Provider、Tool、Memory、Middleware 可通过稳定协议扩展。
7. 运行事件按 Run sequence 保存并通过 SSE 重放。
8. 后台对真实 API 可用；断开时明确标记演示模式。
9. SQLite 和 in-process bus 支持本地，并提供单副本容器部署制品；这不等同可恢复云集群。
10. Agent/provider 配置拒绝常见明文凭据键，页面不持久化控制密钥；模型输出、工具错误与
    异常事件的全链路净化仍是后续安全门禁。

## 非目标（0.1.0）

- 不承诺多区域、高可用、exactly-once 外部副作用。
- 不承诺未知插件的安全在线安装。
- 不实现完整 OIDC/RBAC、KMS/Vault 或数据库 RLS。
- 不把 LLM 文本质量当作确定性单元测试结果。
- 不保存或展示原始 chain-of-thought。

## 成功标准

- 后端单测/集成测、前端 lint/typecheck/build/SSR 测试全部通过。
- 从后台可创建多个数据库 Agent 和不可变 revision。
- 在完成真实模型配置后，通过后台发起委派 Run，事件包含
  `delegation.started`、`delegation.completed`、`run.completed`。
- 静态环用例不能运行。
- 全局 step 预算对子 Agent 生效。
- Provider、Tool、Memory、Storage、Event Bus、Scheduler、Middleware、UI
  均出现在扩展目录。

## 路线图

### 0.2：可恢复执行

显式 Run/Invocation 状态机、checkpoint、outbox、idempotency key、lease/fencing、
崩溃恢复与取消树。

### 0.3：云适配

PostgreSQL、Redis/NATS、对象存储、OpenTelemetry、SecretRef、迁移和 Helm。

### 0.4：治理

OIDC/RBAC/ABAC、审批恢复、审计、插件进程隔离、签名/SBOM、TCK 兼容矩阵。

### 1.0：稳定协议

Durable peer session、MCP、A2A、AG-UI、正式 Plugin API/Event/HTTP 稳定承诺。
