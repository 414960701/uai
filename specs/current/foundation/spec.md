---
kind: normative
id: SPEC-FOUNDATION
status: active
version: 1.0.0
last_reviewed: 2026-07-30
---

# Foundation capability

本目录是 UAI Forge 核心资源、运行、多 Agent、扩展、安全和部署能力的当前规范基线。

- [需求](requirements.md)
- [设计](design.md)
- [任务与路线](tasks.md)
- [追踪矩阵](traceability.md)
- [公共合同](contracts/)

“当前规范”同时记录真实实现状态和已冻结的后续契约。只有标为 `Implemented` 且有自动化
证据的能力可以对外宣称已经交付；`Partial`、`Specified`、`Planned` 不能被产品文案或
部署说明写成已完成。

## 版本范围

| 范围 | 状态 |
|---|---|
| `0.1.x` 单进程 Agent/Instance/bounded child/SSE 基线 | 当前实现 |
| `0.2` 显式状态机、checkpoint、outbox、lease | 已规定验收条件，未实现 |
| `0.3` PostgreSQL、durable bus、OTel、SecretRef | 设计目标 |
| `0.4` OIDC/RBAC、审批、插件隔离 | 设计目标 |
| `1.0` durable peer、MCP/A2A/AG-UI 稳定合同 | 方向已确认，协议仍需实现验证 |
