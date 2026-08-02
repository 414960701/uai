---
kind: normative
id: SPEC-FOUNDATION-DESIGN
status: accepted
version: 1.0.0
last_reviewed: 2026-07-30
---

# Foundation design

## 决策来源

- [协议优先核心](../../../docs/architecture/adr/ADR-0001-protocol-first-core.md)
- [版本化资源](../../../docs/architecture/adr/ADR-0002-versioned-resources.md)
- [Agent revision 直接运行](../../../docs/architecture/adr/ADR-0008-agent-revision-run-targets.md)
- [Agent 草稿/发布生命周期](../../../docs/architecture/adr/ADR-0009-agent-draft-publish-lifecycle.md)
- [双多 Agent 语义](../../../docs/architecture/adr/ADR-0003-dual-agent-collaboration.md)
- [插件信任边界](../../../docs/architecture/adr/ADR-0004-plugin-trust.md)
- [可恢复执行提案](../../../docs/architecture/adr/ADR-0005-at-least-once-recovery.md)
- [工具凭证只通过加密资源引用](../../../docs/architecture/adr/ADR-0012-tool-credentials.md)
- [Git 工作流工具](../../../docs/architecture/adr/ADR-0015-git-workflow-tool.md)
- [Follow-up Conversation 工具](../../../docs/architecture/adr/ADR-0014-follow-up-conversation-tool.md)

## 分层

```text
Web / CLI / HTTP / SSE adapters
             ↓
Application services: registry, run manager, team coordinator
             ↓
Domain: definitions, revisions, sessions, runs, policies, messages
             ↓
Ports: provider, tool, store, bus, workspace, credential, policy, tracer
             ↓
Local / cloud / third-party adapters
```

依赖只向内。领域层不导入 FastAPI、React、AgentScope、LangGraph、厂商 SDK、SQLite 或 Redis。

## 当前核心端口

`0.1.x` 已定义由 UAI Forge 领域类型组成的最小结构化 `Protocol`：

- `RepositoryPort`：图校验和 Run 执行所需的 Agent revision 读取与 Run 读写。
- `EventStorePort`：有序 Run Event 追加、回放与 terminal 查询。
- `EventBusPort`：Runtime/RunManager 的事件发布边界。
- `EventStreamPort`：HTTP/SSE 使用的可选回放与实时订阅面。

`AgentGraphValidator`、`AgentRuntime` 和 `RunManager` 不导入 `SQLiteRepository` 或
`EventBroker`；内置 `SQLiteRepository` / `EventBroker` 通过结构化类型实现端口。当前
只有这组本地适配器，尚无 PostgreSQL、durable bus、adapter 配置生命周期或正式 TCK。
Checkpoint、Outbox、Lease 等恢复端口仍属于后续设计，不能把本次依赖倒置解释为已经
实现 durable cloud。

## 当前数据模型

`0.1.0` SQLite 表：

- `agents`：每 tenant 的 Agent 当前视图；`revision` 是 `latest` 标签指向的快照编号，
  不是历史序列的最大值。
- `agent_revisions`：不可变 revision 历史。
- `agent_revisions.status`：`draft` 或 `published`；`published_at` 只在发布时写入。
- `runs`：Run JSON 与索引状态。
- `run_events`：每 tenant/run 的单调 sequence。
- `tool_credentials`：每 tenant 的工具凭证密文、掩码、metadata 和 version；Agent 只保存 `credential_ref`。

当前模型可以支持单进程控制面，但不能支持 worker lease、checkpoint、outbox 或 peer inbox。

当前 SQLite v3 不读取旧 `instances` 表、旧 Run `instance_id` 或缺失 lifecycle 字段；
遇到这些结构必须备份后重建。Run 从可选的 `agent_revision` 读取不可变快照；缺失时读取
latest 指针，然后把实际 revision 写入 Run。回滚更新当前视图指针，历史表保持不变；继续
发布从历史最大编号之后分配新 revision。

## 目标数据模型

新增资源采用独立表/集合，不把任意插件数据塞入 Run JSON：

| 资源 | 关键字段 |
|---|---|
| `sessions` | tenant, session_id, version, status, policy_context |
| `runs` | definition_revision, state, attempt, parent_run, lease/fencing |
| `invocations` | kind, state, input/output refs, idempotency_key, retry policy |
| `checkpoints` | run, invocation, sequence, state schema, plugin versions |
| `outbox` | intent type, idempotency key, payload ref, delivery state |
| `inbox` | peer session, sender, dedupe key, schema, offset, expiry |
| `approvals` | call hash, actor, decision, scope, expiry, consumed_at |
| `plugin_state` | plugin_id, state_schema_version, owner resource, value/ref |

所有主键或唯一键包含 tenant。大 payload 使用对象存储引用，并带大小、hash 和内容类型。

## Run 事务边界

1. API 创建 `queued` Run。
2. worker 以 compare-and-swap 获取 lease 和 fencing token。
3. worker 读取兼容 checkpoint，编译上下文。
4. 模型或工具调用前创建 Invocation。
5. 无外部副作用的结果与 checkpoint 在一个事务提交。
6. 有副作用时先提交 intent/outbox，再由 dispatcher 调用。
7. dispatcher 以 idempotency key 提交结果；旧 fencing token 不能更新状态。
8. 终态与 terminal event 在一致的事务语义内提交。

`0.1.0` 只实现第 1、部分第 3/4 和第 8 的单进程简化版本。

## Bounded nested call

- `ChildMount` alias 变为模型可见工具名 `delegate_<alias>`。
- 调用使用父 Run ID、Session ID、根预算账本和根并发 semaphore；每个 bounded child
  持有可转让 lease，等待自己的工具/child 时让出、恢复模型循环前重新获取。
- mount semaphore 的身份包含 tenant、父 Agent revision 与 alias，避免跨租户串扰，并让
  新 revision 的 `max_concurrency` 独立生效。
- 每个 bounded invocation 有自己的 step/tool/token ledger 和直接 child semaphore；动作
  同时受根 ledger/根 semaphore 约束。child timeout 覆盖许可等待与执行。
- ancestor 的绝对深度上限与 child 本地相对 `max_depth` 取更严格值。
- child revision 可钉住；未钉住时解析调用开始时子 Agent 的 `latest` 标签。
- path guard 和静态图共同阻止递归。
- child 结果以结构化 tool result 返回父模型。
- `ChildMount.allowed_tools` 以插件 ID 表达 scope；沿树与 ancestor scope 取交集，再叠加
  child ToolBinding permission。`null` 继承，空列表拒绝全部；过滤发生在插件实例化前，
  执行入口再次 fail closed。
- mount 后续仍需增加稳定 binding grant、Secret scope、workspace policy 和输出 schema。

## Durable peer session

durable peer 不复用 `_delegate` 调用栈：

1. Team membership 绑定 Agent 与 Session。
2. sender 写入持久 inbox message，并记录 correlation/causation 和 dedupe key。
3. peer worker 独立领取消息、创建 Run、checkpoint 和回复。
4. Team policy 决定超时、重试、升级、取消传播和成员移除。
5. UI 分别展示消息状态和各 peer Run，不能把它压成一次父工具事件。

## 插件解析

### `0.1.0`

- 发现 PyPA group `uai_forge.plugins`。
- `entry_point.load()` 后调用 `register(registry)`。
- Registry 检查 manifest kind 和协议主版本。
- Registry 按 manifest 声明方言 meta-validate `config_schema` 并缓存 validator；未声明
  `$schema` 时使用 Draft 2020-12。
- API create/PATCH、应用仓储装饰器与 RunManager 分别在写 revision 和创建 Run 前验证
  provider/tool/memory/middleware binding；Runtime 对每个 root/child frame 再验证，覆盖
  历史数据和自定义 Repository 绕过。
- 错误合同使用稳定的 `plugin.not_found`、`plugin.kind_mismatch`、
  `plugin.schema_invalid`、`plugin.config_invalid`、`plugin.unavailable` 和
  `plugin.factory_missing`，只包含 plugin/kind/path/keyword，不包含配置值。
- ToolCall 在 middleware 前按 `ToolPlugin.parameters` 校验，middleware 改写后在
  `invoke()` 前复验；delegate 工具使用同一 JSON Schema guard。错误只暴露 tool/path/
  keyword。
- disabled memory 不实例化；`memory.in_process` 为每个 binding 创建独立策略 view，
  共享底层 session 数据但不共享 `max_messages`。
- 导入异常进入诊断，不阻止整个控制面。

### 目标

```text
discover metadata
  → parse package manifest
  → core/protocol/schema compatibility
  → permission/trust review
  → state migration readiness
  → choose in-process / isolated / remote loader
  → import and register
  → run TCK health check
```

安全、身份、tenant、policy 和 approval 不是普通 middleware。它们位于不可绕过的核心决策链；
插件只可补充更严格规则。普通 trace exporter 失败可降级，但须暴露诊断。

## 协议兼容

- `plugin-manifest.schema.json` 和 `run-event.schema.json` 描述当前 `0.1` 跨边界 JSON。
- `plugin-package-manifest.v2.proposed.schema.json` 和
  `event-envelope.v2.proposed.schema.json` 描述后续协议提案。
- 当前与提案使用不同 `$id`，消费者不得把 v2 required 字段反向要求旧事件。
- 主版本不兼容时拒绝；同主版本消费者忽略未知可选字段。
- payload、插件 state 和 core API 分别版本化。

## 安全

- tenant 必须来自认证上下文，不接受不可信 header 作为生产身份。
- ModelConfig 和 ToolCredential secret 在适配器边界解析；数据库只保存密文，Agent 只保存配置 ID 或 `credential_ref`。
- `tool.git` 的外部同步由 binding 固定 repository root、remote name 和 `credential_ref`；提供
  常规 status/diff/pull/commit/push 工作流，但不提供任意 Git 命令、force push、远端删除或冲突自动解决。
- `tool.conversation` 只能通过 `RunSubmissionPort` 提交新的 UAI Forge Run；它不绕过 Agent/revision、
  session、拓扑、权限、超时或预算校验。
- approval 是服务端记录，不是 request metadata。
- high-impact tool 使用 policy → approval → budget 顺序。
- 未知 Python 插件与宿主等权，只能作为受信任代码或隔离。
- 原始 CoT 不进入持久化、事件和 UI。

完整处置见
[威胁模型](../../../docs/architecture/threat-model.md)。

## 部署

- Local：SQLite + in-process broker + 单 Python 进程。
- Single-node container：同样语义，单 worker 与持久 volume。
- Durable cloud：PostgreSQL + durable bus + workers + object store + KMS + OTel。

部署模式改变适配器，不改变 Agent/Run/Event/Plugin 领域合同。详见
[部署设计](../../../docs/architecture/deployment.md)。
