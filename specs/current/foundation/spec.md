---
kind: normative
id: SPEC-FOUNDATION
status: active
version: 1.0.0
last_reviewed: 2026-08-01
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

CHG-0010 的控制面产品化能力已在当前工作树以 additive API、SQLite compatibility gate、
类型化前端状态和 SSE projection 形式落地；其浏览器级首用、键盘/缩放和真实 Provider
在线检查证据仍按 change acceptance 与全局追踪矩阵单独计状态。该 change 尚未把当前
`0.1.x` 单进程基线升级成分布式恢复、可信多租户或生产级身份系统。

CHG-0030 为当前基线增加受限的 `tool.web_search` / `tool.web_fetch` / `tool.web_json` /
`tool.web_rss` 只读工具，并为新建 Agent 提供六项安全基础工具和更宽裕的多步执行默认值；浏览器自动化、文件系统、代码执行
和业务系统连接仍不属于默认能力，也不改变单进程、非生产级隔离边界。

`CHG-0031-agent-draft-publish-editor` 为 Agent 增加 draft/published revision 生命周期、latest 标签、回滚/继续编辑和
状态化版本选择 UI；当前 SQLite v3 对旧 Instance/`instance_id` 结构 fail closed，要求
backup/rebuild，不执行旧数据迁移。

`CHG-0031-extensible-sandbox-runtimes` 增加自有 `SandboxProvider` 扩展端口和显式 opt-in 的 `sandbox.docker` /
`tool.sandbox_exec`；当前只证明 argv builder、registry 和本地边界，不声称已经具备生产级
容器逃逸防护、rootless/dedicated executor、镜像供应链或多租户沙箱服务。

## 版本范围

| 范围 | 状态 |
|---|---|
| `0.1.x` 单进程 Agent revision/bounded child/SSE 基线 | 当前实现 |
| `0.2` 显式状态机、checkpoint、outbox、lease | 已规定验收条件，未实现 |
| `0.3` PostgreSQL、durable bus、OTel、SecretRef | 设计目标 |
| `0.4` OIDC/RBAC、审批、插件隔离 | 设计目标 |
| `1.0` durable peer、MCP/A2A/AG-UI 稳定合同 | 方向已确认，协议仍需实现验证 |
