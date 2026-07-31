---
kind: plan
id: SPEC-FOUNDATION-TASKS
status: active
version: 1.0.0
last_reviewed: 2026-07-31
---

# Foundation tasks

勾选只表示当前工作树存在对应实现和测试，不表示整个阶段完成。

## Wave 0：规范与单进程基线

- [x] `TASK-001` 建立自有 Pydantic Agent、Binding、Run 与 Event 合同。
  需求：`CORE-001`, `PROTO-001`
- [x] `TASK-002` 保存 Agent 最新视图和不可变 revision，加入乐观并发。
  需求：`CORE-002`
- [x] `TASK-003` 建立 Instance CRUD 和 revision 引用。
  需求：`CORE-003`（仅部分完成）
- [x] `TASK-004` 实现 mount 图检查和 bounded child。
  需求：`MAG-001`, `MAG-002`
- [x] `TASK-005` 实现共享预算、并发和 Run terminal event。
  需求：`MAG-003`, `RUN-001`（生命周期仅部分）
- [x] `TASK-006` SQLite Run Event sequence、回放和 SSE。
  需求：`RUN-002`
- [x] `TASK-007` 插件能力目录与协议主版本拒绝。
  需求：`EXT-001`
- [x] `TASK-008` Web live/disconnected 明示、构建、SSR、lint 和 typecheck。
  需求：`UI-002`
- [x] `TASK-009` 将 Instance overrides 通过 Schema allowlist 真正应用到 Runtime。
  需求：`CORE-003`
- [ ] `TASK-010` 完整 Agent revision 编辑、Instance/mount/policy schema 表单。
  需求：`UI-001`（结构化基础字段已完成；Schema 自动表单、Instance override 与 peer 未完成）
- [x] `TASK-011` 让图 validator 沿 mount 钉住的 revision 递归并补正反例。
  需求：`MAG-001`
- [x] `TASK-012` 修复嵌套委派重入根 semaphore 的单槽死锁。
  需求：`MAG-006`
- [ ] `TASK-013` 将 Definition 删除改为 archive/tombstone 并定义同 ID 重建。
  需求：`CORE-005`
- [x] `TASK-014` 隔离 EventBroker 慢订阅者 `QueueFull`。
  需求：`RUN-008`
- [x] `TASK-015` 抽取执行核心最小 Repository/Event Port，并用非 SQLite 替身完成真实 Run。
  需求：`EXT-005`
- [x] `TASK-016` 增加高级 Agent revision/mount/plugin 配置、多 Instance 启停和真实事件视图。
  需求：`UI-001`, `UI-002`, `RUN-002`
- [x] `TASK-017` 实现 child 本地预算/timeout/depth/并发与 mount 工具 scope 交集。
  需求：`MAG-003`, `MAG-006`, `MAG-007`
- [x] `TASK-018` 实现插件 config、工具/委派 arguments 的 JSON Schema fail-closed
  边界，并修复 memory binding 启用与独立策略语义。
  需求：`EXT-006`
- [x] `TASK-019` 增加隔离的单节点容器 build/start/health/doctor/空数据库 smoke，
  接入 Makefile 并同步部署状态。
  需求：`DEP-002`
- [x] `TASK-020` 锁定公开发布 Web 依赖，在本地发布门禁和裁剪后的 Web 运行镜像加入
  production-only high/critical audit 门禁，审查完整开发工具链 audit 并复跑兼容性门禁。
  需求：`SEC-006`
- [x] `TASK-021` 将个人 Sites 元数据移出公开源码和 Docker context，提供中性示例与
  缺省构建路径，并增加仓库卫生测试和发布扫描。
  需求：`SEC-007`
- [x] `TASK-022` 统一租户 ModelConfig、Claude Messages 协议、Provider 模型目录和
  “凭证&模型配置”控制台入口；Agent 只保存 `model_config_id`。
  需求：`CFG-001`, `SEC-001`, `EXT-007`, `UI-001`

## Wave 1：可恢复执行 `0.2`

- [ ] `TASK-101` 增加 Session、Invocation、Checkpoint、Outbox、Approval 和 Lease 模型/迁移。
  需求：`CORE-004`, `RUN-003`, `RUN-004`, `RUN-005`, `SEC-004`
- [ ] `TASK-102` 用显式 reducer 和 compare-and-swap 替换隐式 Run 状态赋值。
  需求：`RUN-001`
- [ ] `TASK-103` 增加 worker lease、fencing token 和恢复扫描器。
  依赖：`TASK-101`, `TASK-102`；需求：`RUN-003`, `RUN-005`
- [ ] `TASK-104` 增加副作用 intent/outbox dispatcher 和工具幂等 capability。
  依赖：`TASK-101`；需求：`RUN-004`
- [ ] `TASK-105` 持久 parent/child invocation 和取消树。
  依赖：`TASK-101`, `TASK-102`；需求：`RUN-006`
- [ ] `TASK-106` 实现服务端 Approval 签发/消费 API、等待状态与恢复流程；继续拒绝
  metadata 自报批准（伪造防护已在 `0.1` 完成）。
  依赖：`TASK-101`；需求：`SEC-004`
- [ ] `TASK-107` 升级到事件信封 v2，同时保留 v1 读取适配。
  依赖：`TASK-102`；需求：`PROTO-002`, `OBS-001`
- [ ] `TASK-108` 完成崩溃窗口、重复副作用、旧 worker 和取消竞态测试。
  依赖：`TASK-103`—`TASK-107`
- [ ] `TASK-109` 将 Run terminal transition、canonical event 和 outbox 合并为一个事务。
  需求：`RUN-007`

## Wave 2：云端口与插件治理 `0.3`

- [ ] `TASK-201` 将当前最小 Repository/Event Port 扩展为正式 adapter TCK，并补齐
  Checkpoint、Outbox、durable Bus 与 Lease 自有 Protocol。
- [ ] `TASK-202` PostgreSQL adapter 与正式迁移。
- [ ] `TASK-203` Redis Streams 或 NATS JetStream adapter、DLQ 和 backpressure。
- [ ] `TASK-204` SecretRef、CredentialResolver 与泄露测试。
- [ ] `TASK-205` 插件 package manifest v2、导入前验证和状态迁移。
- [ ] `TASK-206` 将安全 hook 与普通 middleware 分层并测试 fail closed。
- [ ] `TASK-207` OpenTelemetry trace/metric 与脱敏 correlation。
- [ ] `TASK-208` worker kill、重复 delivery、网络分区和迁移演练。

## Wave 3：安全与隔离 `0.4`

- [ ] `TASK-301` OIDC identity 与可信 tenant binding。
- [ ] `TASK-302` RBAC/ABAC、审计和短时令牌。
- [ ] `TASK-303` 插件隔离进程/容器、签名、SBOM 和管理员审批。
- [ ] `TASK-304` WorkspaceProvider 与 none/read-only/copy-on-write/shared 策略。
- [ ] `TASK-305` SSRF、路径逃逸、egress 和资源配额测试。

## Wave 4：Durable collaboration `1.0`

- [ ] `TASK-401` Team、Membership、PeerSession 和 InboxMessage 合同。
- [ ] `TASK-402` durable peer worker、去重、回复和取消 policy。
- [ ] `TASK-403` MCP 工具 adapter 与安全 gateway。
- [ ] `TASK-404` A2A remote peer adapter。
- [ ] `TASK-405` AG-UI 事件 adapter 与 v2 event mapping。
- [ ] `TASK-406` Control Center 的 bounded/peer 双拓扑与消息运行视图。
- [ ] `TASK-407` 多进程端到端恢复、安全和兼容矩阵。
