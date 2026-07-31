---
kind: evidence-index
id: SPEC-FOUNDATION-TRACEABILITY
status: active
version: 1.0.0
last_reviewed: 2026-07-31
---

# Foundation traceability

机器可读明细位于 [`specs/traceability.yaml`](../../traceability.yaml)。本表用于评审，不替代
测试输出。

| Requirement | 状态 | 当前实现证据 | 自动化证据或缺口 |
|---|---|---|---|
| `CORE-001` | Implemented | `models.py`, `ports.py` | Registry/API/runtime tests 使用自有类型 |
| `CORE-002` | Implemented | `storage.py` revisions | `test_agent_updates_are_versioned_and_optimistic` |
| `CORE-003` | Partial | strict Instance override、effective spec、Run context | policy 收紧/上下文/不可变性有测；缺正式 deployment profile 与已有 Instance 容量热更新 |
| `CORE-004` | Specified | 仅 `session_id` | 缺 Session store/version/permission tests |
| `CORE-005` | Specified | 当前硬删除 latest row | 同 ID 重建可能 revision 唯一键失败 |
| `CORE-006` | Specified | 当前一个可由客户端写的 status | 缺 controller reconcile/generation |
| `RUN-001` | Partial | `RunManager` | 基本 lifecycle 有测；缺 wait/pause/CAS |
| `RUN-002` | Implemented | `run_events`, `EventBroker` | history cursor、SSE `Last-Event-ID` tail、订阅注册/replay 窗口与慢订阅者回归均通过 |
| `RUN-003` | Specified | 无 checkpoint | 缺 worker crash/recovery |
| `RUN-004` | Specified | 无 outbox | 缺重复副作用测试 |
| `RUN-005` | Specified | 无 lease/fencing | 缺旧 worker 写拒绝 |
| `RUN-006` | Partial | `asyncio.Task.cancel()` | 缺持久取消树和重启传播 |
| `RUN-007` | Specified | Run update 与 terminal event 分事务 | 缺原子故障注入测试 |
| `RUN-008` | Implemented | EventBroker 有界 queue + 慢订阅者断开 | `test_slow_subscriber_is_disconnected_without_failing_publish` |
| `PROTO-001` | Implemented | `/api/v1`, Pydantic | `test_control_plane_crud_and_capabilities` |
| `PROTO-002` | Specified | v1 `RunEvent` | v2 proposed Schema，无 producer |
| `MAG-001` | Implemented | `graph.py`, `run_manager.py` | child mount 与 pinned root instance 的 pinned/latest 拓扑正反例均有测试 |
| `MAG-002` | Implemented | `runtime.py::_delegate` | `test_mounted_agent_executes_as_guarded_tool` |
| `MAG-003` | Implemented | root + invocation ledger、root/local/mount semaphore、child timeout/depth | 宽根/窄 child 的 step/tool/token/time/parallel/depth 正反例和许可恢复均有测试 |
| `MAG-004` | Specified | 无 Team/Inbox | 缺 peer contract 和 E2E |
| `MAG-005` | Planned | 无 WorkspaceProvider | 等待接口与 sandbox 设计 |
| `MAG-006` | Implemented | `RootConcurrencyLease` | `test_three_level_delegation_with_one_root_slot_does_not_deadlock` |
| `MAG-007` | Implemented（bounded 工具） | mount plugin-ID scope 沿树交集 + child permission | null/空/显式允许、ancestor 不可扩权、deny 与伪造调用均有测试；完整身份/Secret/workspace/Approval 权限仍缺 |
| `EXT-001` | Implemented | `PluginRegistry` | `test_incompatible_plugin_protocol_fails_closed` |
| `EXT-002` | Specified | 当前直接 entry-point load | v2 proposed Schema，无 preflight loader |
| `EXT-003` | Specified | 普通 middleware | 缺不可绕过 PolicyEngine |
| `EXT-004` | Specified | 无 plugin state | 缺 namespace/migration TCK |
| `EXT-005` | Implemented（最小边界） | `RepositoryPort`、`EventStorePort`、`EventBusPort`、`EventStreamPort` | 非 SQLite/EventBroker 替身真实 Run + 内置适配器结构符合性测试；仍仅一套生产 adapter |
| `EXT-006` | Implemented | Registry Schema cache、API/Repository/Run/Runtime gates、Tool/delegate argument guard、binding-local memory policy | `test_plugin_config_validation.py`、`test_tool_argument_validation.py`、`test_memory_bindings.py` |
| `SEC-001` | Partial | provider env reference + 配置边界明文拒绝 | 创建/PATCH/Run metadata 有测；缺通用 SecretRef 与全输出泄露测试 |
| `SEC-002` | Partial | tenant-scoped SQLite | `test_tenant_data_is_isolated`；header 不可信 |
| `SEC-003` | Planned | 可选共享 API key | 缺 OIDC/RBAC/ABAC |
| `SEC-004` | Partial | confirm fail-closed；服务端清空客户端审批声明 | 伪造防护有测；缺 Approval API 与恢复流程 |
| `SEC-005` | Partial | 未持久化专门 CoT block | 缺 provider raw/log 泄露测试 |
| `SEC-006` | Implemented | 锁定兼容依赖、CI production audit、裁剪 Web 运行镜像 | `npm ci`、production-only audit、lint/typecheck/test 与镜像内 audit 通过；完整开发链剩余项记录在 CHG-0005 |
| `SEC-007` | Implemented | 忽略真实 hosting 元数据、提交中性示例、Vite 缺省加载 | 无真实 hosting 文件的 lint/typecheck/build/4 项测试、容器 smoke 与当前树/历史扫描通过；证据见 CHG-0006 |
| `UI-001` | Partial | 高级 revision/mount plugin scope/plugin/Instance 编辑与真实 history | SSR/源合同测试 + rev 2、第二 Instance、17 条事件浏览器 E2E；缺 Schema 自动表单、Instance override、revision diff 与 peer |
| `UI-002` | Implemented | live/demo state | `rendered-html.test.mjs` 静态连接契约 |
| `OBS-001` | Partial | Run Event/metrics | 缺 OTel/correlation/脱敏 |
| `DEP-001` | Implemented | CLI/FastAPI/SQLite/Web | backend + frontend 门禁 |
| `DEP-002` | Implemented | 已验证单节点 Docker/Compose 与 SQLite volume；Kubernetes 单副本清单是未实测示例 | `scripts/container-smoke.sh` + CI：双镜像、双健康容器、doctor、真实委派、连续事件与隔离清理 |
| `DEP-003` | Planned | 无正式云 adapter | 需 Postgres/bus/chaos |
