---
kind: design-delta
id: CHG-0029-DESIGN
status: accepted
target: 0.1
---

# Design decisions

1. `RunRequest` 使用 `agent_id: str` 和 `agent_revision: int | null`；解析层统一调用
   `RepositoryPort.get_agent(tenant, agent_id, revision)`，`null` 表示读取 Agent 上的
   `latest` 指针，而不是取历史表中的最大 revision。
2. `RunManager` 在创建 Run 前完成 revision、拓扑和运行时校验，并把实际 revision
   写入 `RunRecord.agent_revision` 与 `metrics.root_revision`。
3. 前端在 RunModal 中先选择 Agent，再从 `/agents/{agent_id}/revisions` 加载版本列表；
   默认值为“最新版本”，提交时省略 `agent_revision`。版本列表用 Agent 当前视图的
   revision 标记 `latest`，因此回滚后标签会随指针移动。
4. 移除 `/instances` 控制面 API、SetupStatus 的 instances 资源、Instance 运行上下文、
   Instance semaphore 和独立管理页面。旧 SQLite 表/旧 Run 字段不做破坏性删除。
5. Agent 的 child mount 以可选 `revision` 表达版本选择；省略该字段时由运行时解析
   子 Agent 的 `latest`。
6. 旧的 CHG-0001/CHG-0002 Instance 证据保留为历史变更记录；本变更的 traceability
   成为当前 0.1.x 运行路径的证据。
