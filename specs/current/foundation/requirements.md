---
kind: normative
id: SPEC-FOUNDATION-REQUIREMENTS
status: active
version: 1.0.0
last_reviewed: 2026-07-31
---

# Foundation requirements

## 解释

- `Implemented`：代码和自动化测试均有证据。
- `Partial`：部分条件成立，仍有明确缺口。
- `Specified`：行为已冻结，等待实现。
- `Planned`：方向存在，公共合同尚未稳定。

所有 SHALL 都是验收条件；状态只描述 2026-07-31 的工作树事实。

## 核心资源

### CORE-001 — 自有领域合同

状态：`Implemented`，目标版本：`0.1`

WHEN 核心、API 或插件交换 Agent、消息、工具或运行数据
THE SYSTEM SHALL 使用 UAI Forge 自有 Pydantic/JSON Schema 合同，不暴露第三方
Agent 框架领域类型。

### CORE-002 — 不可变 Agent 修订

状态：`Implemented`，目标版本：`0.1`

WHEN Agent 定义被更新
THE SYSTEM SHALL 使用乐观并发创建递增 revision，并保留可按 revision 读取的旧快照。

### CORE-003 — 定义与实例分离

状态：`Partial`，目标版本：`0.2`

WHEN 同一 Agent 定义部署为多个 Instance
THE SYSTEM SHALL 让每个 Instance 独立声明 revision、environment、capacity 和经过
Schema 限制的 override，且运行实际使用这些值。

`0.1.x` 已用显式、默认拒绝的 Schema 将 `config_overrides` 限制为 execution policy，
运行时对数值上限取 definition/Instance 的较小值、对 `fail_fast` 取更严格值，并构造
完整复验且不写回 revision 的 effective spec。Instance ID 与 environment 标识会进入
Run metrics、`run.started` 和插件上下文。

当前缺口：environment 仍只是单进程适配器可见标识，不是正式 deployment profile；
已有 Instance 的 `max_concurrency` 更新也不会调整已创建的进程内 semaphore。

### CORE-004 — 一等 Session

状态：`Specified`，目标版本：`0.2`

WHEN 多个 Run 使用同一 Session
THE SYSTEM SHALL 持久保存 Session 状态、权限上下文、版本和并发控制，而不是只使用
字符串 ID 与进程内 Memory。

### CORE-005 — Archive 与引用完整性

状态：`Specified`，目标版本：`0.2`

WHEN Agent Definition 已有 Revision、Instance 或历史 Run 引用
THE SYSTEM SHALL 使用 archive/tombstone 而不是破坏历史的硬删除；同 ID 重建必须返回
确定性冲突或显式恢复流程，不能产生数据库唯一键异常。

当前删除 latest row 会保留 revision row，同 ID 重建 revision 1 可触发底层唯一键错误。

### CORE-006 — Instance desired/observed state

状态：`Specified`，目标版本：`0.3`

WHEN Instance 被启动、停止或云端 controller 协调
THE SYSTEM SHALL 分离 desired state、observed state、generation 和 deployment profile；
普通客户端不能直接自报 observed `ready`。

## Run 与事件

### RUN-001 — 显式生命周期

状态：`Partial`，目标版本：`0.2`

WHEN Run 被提交、暂停、等待输入/审批、恢复、完成、失败或取消
THE SYSTEM SHALL 只允许规范状态机中的 compare-and-swap 转换，并记录转换原因。

当前仅实现 `queued → running → succeeded|failed|cancelled`。

### RUN-002 — 有序持久事件与续播

状态：`Implemented`（单进程），目标版本：`0.1`

WHEN Run Event 被发布或 SSE 客户端携带 `after_sequence` 重连
THE SYSTEM SHALL 先持久化 Run 内递增 sequence，再按顺序交付尚未确认的事件。

### RUN-003 — Checkpoint 与崩溃恢复

状态：`Specified`，目标版本：`0.2`

WHEN worker 在模型、工具或子 Agent 边界崩溃
THE SYSTEM SHALL 从最近兼容 checkpoint 恢复，钉住所用 Agent Revision、策略和插件版本，
且不得把旧 `running` 记录盲目从头执行。

### RUN-004 — 幂等副作用与 Outbox

状态：`Specified`，目标版本：`0.2`

WHEN 外部副作用可能被重复投递
THE SYSTEM SHALL 在事务中保存 intent/outbox 和稳定 idempotency key；不可幂等动作不得
自动重试。

### RUN-005 — Lease 与 Fencing

状态：`Specified`，目标版本：`0.2`

WHEN Run 被 worker 领取或 lease 过期后重领
THE SYSTEM SHALL 使用递增 fencing token 拒绝旧 worker 的迟到写入。

### RUN-006 — 取消树

状态：`Partial`，目标版本：`0.2`

WHEN 父 Run 被取消
THE SYSTEM SHALL 持久传播取消到全部 bounded child，并按 Team policy 通知 durable peer。

当前 Python Task 取消通常会中断嵌套调用，但没有持久 parent/child Run 树和重启后传播。

### RUN-007 — 终态、事件与 Outbox 原子一致

状态：`Specified`，目标版本：`0.2`

WHEN Run 进入 terminal 状态
THE SYSTEM SHALL 在同一数据库事务或可证明的一致性协议内提交 Run 状态、canonical
terminal event 和 outbox，不能出现成功 Run 缺 terminal event。

### RUN-008 — 慢订阅者隔离

状态：`Implemented`，目标版本：`0.1`

WHEN SSE 订阅者 queue 满或断开
THE SYSTEM SHALL 断开或降级该订阅者并让其从持久 sequence 追赶，不得令已经持久化的
事件 publish 抛错并使 Run 失败。

当前实现清空该订阅者的有界 live queue、投递断开信号并保留 SQLite 事件；客户端可按
最后收到的 sequence 重连补播。

### PROTO-001 — HTTP API 版本

状态：`Implemented`，目标版本：`0.1`

WHEN 外部客户端调用控制面
THE SYSTEM SHALL 使用 `/api/v1` 版本路径和由 Pydantic 生成的 OpenAPI 合同。

### PROTO-002 — 稳定事件信封

状态：`Specified`，目标版本：`0.2`

WHEN 事件跨进程、跨协议或长期持久化
THE SYSTEM SHALL 包含 event spec version、tenant/session/run/event/correlation/causation
标识、sequence、timestamp 和 payload schema version。

当前 `RunEvent` 是较小的 `0.1` 内部/HTTP 合同，不得称为完整分布式事件信封。

## 多 Agent

### MAG-001 — 静态 Mount 图验证

状态：`Implemented`，目标版本：`0.1`

WHEN Agent 图被验证或发起 Run
THE SYSTEM SHALL 拒绝缺失节点、禁用节点、缺失钉住 revision 和静态 mount 环。

validator 沿 mount 的实际 pinned revision 递归，以 `(Agent ID, revision)` 记录访问状态；
RunManager 校验本次实际执行的 root revision，而不是同 ID 的 latest。“旧 revision
无环、latest 有环”及相反方向在 child mount 和 pinned root instance 上均有回归测试。

### MAG-002 — Bounded nested call

状态：`Implemented`，目标版本：`0.1`

WHEN Parent 通过 `ChildMount` 调用子 Agent
THE SYSTEM SHALL 把子 Agent 作为父 Run 内的受限工具调用，使用结构化输入/输出并产生
delegation 事件。

### MAG-003 — 根预算覆盖调用树

状态：`Implemented`，目标版本：`0.1`

WHEN 父 Agent、工具或 bounded child 消耗 step、tool call、token、时间或并发
THE SYSTEM SHALL 从同一根预算和根并发限制中扣减，并同时遵守子 Agent 本地上限。

每次 bounded invocation 使用本地 ledger，同时复用根 ledger；step、tool call 和 token
均受双层约束。child timeout 包含许可等待与执行；并发同时取得根、父 invocation 和 mount
许可。ancestor 剩余深度与 child 本地 `max_depth` 取更严格值。对应的宽根/窄 child
正反例、timeout 后许可恢复和三 child fan-out 峰值均有自动化测试。

### MAG-004 — Durable peer session

状态：`Specified`，目标版本：`1.0`

WHEN Agent 以长期 peer 身份加入 Team
THE SYSTEM SHALL 为其创建独立 Session/Run/inbox，通过版本化、可去重消息通信，并允许
生命周期长于发起方 Run。

### MAG-005 — Workspace 共享策略

状态：`Planned`，目标版本：`0.4`

WHEN 父子或 peer 需要访问 workspace
THE SYSTEM SHALL 显式选择 `none`、`read_only`、`copy_on_write` 或受审计的 `shared`；
默认不得继承共享写权限。

### MAG-006 — 任意深度并发无死锁

状态：`Implemented`，目标版本：`0.1`

WHEN bounded child 在根并发限制为 1 时继续调用下一层 child
THE SYSTEM SHALL 以顺序执行或可重入安全的容量模型完成，不得在持有根 permit 时再次等待
同一个 permit；任意时刻并发峰值不得超过 root、Instance 和 mount 的有效最小值。

bounded child 使用所有权可检查的根并发 lease；等待下一层调用时让出 permit，取消或
异常展开时只释放实际持有的 permit。三层、根并发为 1 的短超时回归测试已通过。

### MAG-007 — Mount 工具范围交集

状态：`Implemented`（bounded 插件工具），目标版本：`0.1`

WHEN bounded child 或其后代暴露或执行插件工具
THE SYSTEM SHALL 将 ancestor 有效范围、当前 `ChildMount.allowed_tools` 与 child 已启用
ToolBinding/permission 取交集；后代不得恢复 ancestor 已移除的插件。

`allowed_tools` 使用 `ToolBinding.plugin_id`。缺失或 `null` 表示兼容旧 mount、只继承
上游范围；`[]` 表示拒绝 subtree 内全部插件工具。范围外或 child `deny` 的工具不实例化、
不暴露；provider 伪造调用仍在 middleware/tool/event 之前拒绝。

当前边界只覆盖 bounded subtree 的插件工具。tenant PolicyEngine、稳定 binding grant、
Secret/workspace scope、可消费 Approval 和 durable peer 权限仍未实现，不得把本要求解释为
完整身份授权系统。

## 插件与扩展

### EXT-001 — 插件目录与协议主版本

状态：`Implemented`，目标版本：`0.1`

WHEN 内置或 entry-point 插件注册
THE SYSTEM SHALL 校验插件 kind 与核心支持的协议主版本；主版本不兼容时 fail closed。

### EXT-002 — 导入前 Package Manifest

状态：`Specified`，目标版本：`0.3`

WHEN 第三方插件包被发现
THE SYSTEM SHALL 在导入可执行 Python 前读取 manifest，校验 core 范围、实现入口、
配置/状态 schema、权限、信任级和迁移。

当前 entry point 直接 `load()`，只允许受信任管理员预安装。

### EXT-003 — Hook 失败模式

状态：`Specified`，目标版本：`0.3`

WHEN 安全、身份、tenant、权限或审批 hook 出错
THE SYSTEM SHALL fail closed；只有非关键观测 hook 可 fail open，并记录 degraded 诊断。

### EXT-004 — 插件状态命名空间与迁移

状态：`Specified`，目标版本：`0.3`

WHEN 插件保存或升级状态
THE SYSTEM SHALL 使用 `plugin_id/state_schema_version` 命名空间和事务化逐版本迁移；
插件不得任意写 Session 顶层状态。

### EXT-005 — 核心存储与事件端口

状态：`Implemented`（最小单进程边界），目标版本：`0.1`

WHEN 图校验、Agent Runtime 或 RunManager 读取资源、写 Run 或发布事件
THE SYSTEM SHALL 只依赖由 UAI Forge 领域合同组成的 `RepositoryPort` / `EventBusPort`，
且一个不导入 SQLite/EventBroker 的结构化替身可以完成真实 Run。

内置 `SQLiteRepository` / `EventBroker` 结构化实现这些端口，EventBroker 另通过
`EventStorePort` 持久化和回放事件。当前没有第二套生产 adapter、正式 adapter TCK、
PostgreSQL、durable bus、Checkpoint/Outbox/Lease 端口；因此本要求不代表 durable cloud
或多 worker 已实现。

### EXT-006 — 插件绑定与调用 Schema fail closed

状态：`Implemented`，目标版本：`0.1`

WHEN provider、tool、memory 或 middleware manifest 注册、Agent revision 创建/更新、
Run 提交或运行时从任意 Repository 读取 Agent
THE SYSTEM SHALL 先验证 `config_schema` 自身是受支持的 JSON Schema，再按对应 kind 与
manifest 校验完整 binding config；未知插件、kind 不匹配、无效 Schema、不可用插件和无效
配置必须以稳定错误码 fail closed，且错误不得回显配置值。

WHEN provider 返回 ToolCall 或 middleware 改写 arguments
THE SYSTEM SHALL 在 middleware 前按 `ToolPlugin.parameters` 校验一次，并在实际
`invoke()` 前对改写后的 arguments 再校验；bounded delegation 使用同等的
required/type/additionalProperties/maxLength 合同。参数错误与工具参数 Schema 错误不得
回显参数值。

WHEN `MemoryBinding.enabled=false`
THE SYSTEM SHALL 不创建、不读取也不追加 memory adapter。内置进程内 memory 可共享底层
session 数据，但 retention 等策略必须按每个 binding 生效，不得由首次创建的 binding
锁定后续 Agent 的配置。

## 安全、身份与隐私

### SEC-001 — Secret 只存引用

状态：`Partial`，目标版本：`0.3`

WHEN 模型、工具或插件需要凭据
THE SYSTEM SHALL 持久化 SecretRef 或环境变量名，在受信任边界解析，并保证 Secret 值
不进入配置响应、事件、日志、prompt、trace 或 HTML。

当前 OpenAI-compatible provider 支持环境变量引用；Model、Tool、Memory、Middleware、
Instance override 和 Run metadata 已递归拒绝常见明文 credential key；Agent/Instance
PATCH 会重建完整模型以避免跳过校验。通用 SecretRef/CredentialResolver、插件自定义
敏感字段和日志/异常/HTML 全输出泄露测试仍未完成。

### SEC-002 — 可信租户隔离

状态：`Partial`，目标版本：`0.4`

WHEN 用户访问任何租户资源
THE SYSTEM SHALL 从已认证身份推导 tenant，并在存储、事件、bus 和插件上下文中强制隔离。

当前 Repository 查询带 tenant，但 `X-Tenant-ID` 可由未认证客户端设置，只是分区参数。

### SEC-003 — RBAC/ABAC

状态：`Planned`，目标版本：`0.4`

WHEN 操作者创建、修改、运行、审批或删除资源
THE SYSTEM SHALL 根据短时身份令牌、角色、资源属性和操作风险授权并写入审计。

### SEC-004 — 服务端审批

状态：`Partial`，目标版本：`0.2`

WHEN 工具策略为 `confirm`
THE SYSTEM SHALL 只接受服务端签发、绑定 tenant/run/call hash/expiry 的一次性批准，不接受
Run request metadata 的自报批准。

当前已验证 request metadata 不能注入 `approved_tools`，`confirm` 工具保持 fail closed；
持久 Approval 资源、签发/消费 API、等待审批状态和批准后恢复流程仍未实现。

### SEC-005 — 不持久化原始 CoT

状态：`Partial`，目标版本：`0.2`

WHEN 模型返回 reasoning、thinking 或 provider raw 数据
THE SYSTEM SHALL 不持久化或展示原始 chain-of-thought，只保存最小可审核摘要。

当前事件没有专门的 thinking block，但仍需 provider/日志/异常泄露测试。

### SEC-006 — 公开发布生产依赖门禁

状态：`Implemented`，目标版本：`0.1`

WHEN JavaScript/TypeScript 控制后台准备公开发布
THE SYSTEM SHALL 使用已提交的 `package-lock.json` 与 `npm ci` 解析依赖，完整通过
lint、typecheck、production build/test，并让
`npm audit --omit=dev --audit-level=high` 成功，即 npm 分类的生产依赖图中不存在
high/critical advisory。

WHEN 构建 Web 运行镜像
THE SYSTEM SHALL 裁剪仅构建和开发时使用的依赖，并对镜像内 production graph 重复
执行同一 audit 门禁。

完整开发依赖 audit SHALL 被审查并记录剩余范围；不得使用未经审查的
`npm audit fix --force`、静默降级依赖或升级到未经兼容测试的破坏性主版本。

### SEC-007 — 公开仓库环境元数据隔离

状态：`Implemented`，目标版本：`0.1`

WHEN UAI Forge 源码发布到公开仓库
THE SYSTEM SHALL 不跟踪个人或环境专属的部署项目 ID、真实 Secret、本机绝对路径、运行
数据库或构建状态；真实 `.openai/hosting.json` SHALL 保持本地并被 Git 与 Docker build
context 忽略，公开源码只提供不含 `project_id` 的中性示例。

WHEN 开发者从干净 checkout 检查或构建 Web 控制后台
THE SYSTEM SHALL 在 `.openai/hosting.json` 不存在时使用无 D1/R2 binding 的默认值，且
lint、typecheck、production build/test 和容器构建不得依赖维护者个人部署配置。

## 控制后台与观测

### UI-001 — 管理多个 Agent 与 Instance

状态：`Partial`，目标版本：`0.2`

WHEN Agent 构建者使用 Web 后台
THE SYSTEM SHALL 可创建、查看、修订 Agent，管理多个 Instance、mount 模式和策略，并以
插件 JSON Schema 在服务端驱动验证。

`0.1.x` 已支持创建和发布不可变 Agent 修订，配置 provider/model、工具别名/权限/JSON、
memory、middleware、mount alias/固定 revision/并发/输入模板/下游工具插件范围和执行
策略；也支持创建多个固定 revision 的 Instance、启停、真实 Run history 与 demo/live
明示。

当前仍为 `Partial`：第三方插件配置使用通用 JSON 对象而不是由 manifest JSON Schema
自动生成控件；尚无 Instance policy override 编辑、revision diff、peer session 或
desired/observed deployment controller。

### UI-002 — 真实连接状态

状态：`Implemented`，目标版本：`0.1`

WHEN Control API 不可用
THE SYSTEM SHALL 明确显示 demo mode，且 demo 数据不得被标记为 live 或部署健康证据。

### OBS-001 — 可关联观测

状态：`Partial`，目标版本：`0.3`

WHEN Run、模型、工具或 Agent 调用发生
THE SYSTEM SHALL 产生可通过 correlation/causation 关联的脱敏事件和 OpenTelemetry
trace/metric，不记录 Secret 或原始 CoT。

当前有 Run Event 和预算 metrics，没有完整 OTel 和稳定关联 ID。

## 部署

### DEP-001 — 本地单进程

状态：`Implemented`，目标版本：`0.1`

WHEN 开发者在本地启动 UAI Forge
THE SYSTEM SHALL 使用 Python 3 Runtime、FastAPI、SQLite 和可独立启动的 Web 后台完成
Agent CRUD 与 bounded delegation。

### DEP-002 — 单节点容器

状态：`Implemented`，目标版本：`0.1`

WHEN 使用容器部署 `0.1.x`
THE SYSTEM SHALL 保持单 worker、持久 SQLite volume、健康检查和真实委派 smoke test，
并明确不支持水平扩 worker。

可重复的 Compose 门禁构建两个生产镜像，启动并验证两个健康容器，运行后端 doctor，
再通过 HTTP API 完成 bounded child 委派并校验从 1 连续到终态的事件；2026-07-30
实测为 17 条。测试资源按唯一 project/volume 和动态测试端口隔离，并在结束时验证
容器、network 与 volume 均已清理。

### DEP-003 — 可恢复云适配

状态：`Planned`，目标版本：`0.3`

WHEN 部署多个 API/worker 副本
THE SYSTEM SHALL 使用 PostgreSQL、durable bus、lease/fencing、checkpoint/outbox、
Secret manager 和 OTel，并通过重复投递与 worker kill 测试。
