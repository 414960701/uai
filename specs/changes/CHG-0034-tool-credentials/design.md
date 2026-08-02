---
kind: design-delta
id: CHG-0034-DESIGN
status: accepted
target: 0.1
---

# Design

1. 新增 UAI Forge 自有 `ToolCredential`/`ToolCredentialWrite`/`ToolCredentialPatch` 合同，字段只包含 id、name、kind/provider、metadata、masked_secret、enabled、version 和时间戳；不把 provider SDK 类型或原始 secret 引入核心。
2. SQLite 新增 `tool_credentials` 表。schema v3 → v4 只执行 `CREATE TABLE IF NOT EXISTS`、索引和 `schema_meta` 更新，迁移在现有写事务中完成；不复制、打印或重写既有密文。新数据库直接创建 v4 完整表。
3. Repository 提供 `list/get/save/delete/resolve_tool_credential_secret` 和引用扫描。resolver 只在运行时内部使用，控制 API 没有“读取明文”端点。
4. 控制 API 提供 tenant-scoped `/api/v1/tool-credentials` CRUD 与 `/references` 查询。PATCH 要求版本，删除在事务内检查历史 Agent revisions 的 `credential_ref` 引用。
5. `ToolBinding.config.credential_ref` 是稳定的部署/运行引用。当前内置只读工具不自动消费该字段；后续 Git/外部副作用适配器必须在工具边界调用 resolver，并由自己的 scope/副作用规范限制权限。
6. 控制台在系统导航增加独立页面，secret 输入框使用 password/new-password 语义，列表仅显示掩码、provider、kind、ID 和状态；清除 secret 会同时停用凭证，防止空密文被误用。
