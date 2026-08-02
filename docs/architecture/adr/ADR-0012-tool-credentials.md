---
kind: adr
id: ADR-0012
status: accepted
date: 2026-08-02
supersedes: []
---

# ADR-0012：工具凭证只通过加密资源引用

## 背景

Git、代码托管和其他外部工具需要凭证，但把 token 放进 Agent prompt、工具配置、事件或日志会扩大泄漏面，也会让部署侧轮换覆盖旧 revision。模型配置已有独立的加密生命周期，工具凭证需要同等边界。

## 决策

- 增加 tenant-scoped `ToolCredential` 资源，控制 API 只返回掩码和 metadata。
- secret 使用启动时注入的 `UAI_FORGE_CREDENTIAL_MASTER_KEY` 加密存储；master key 不进入数据库、事件、日志或浏览器。
- Agent tool binding 只保存 `config.credential_ref`。只有受信任的工具适配器在运行时调用内部 resolver，明文不返回给模型或 UI。
- 更新使用 version CAS；清除 secret 自动停用；历史 Agent revision 引用存在时禁止删除。
- SQLite v3 到 v4 使用事务内的 additive migration，保留既有数据；未来 PostgreSQL/KMS 适配器必须保持同一非泄漏合同。

## 后果与边界

该 ADR 只解决凭证生命周期和引用，不等于 Git push、远程仓库固定、分支保护、RBAC、Secret Manager 或生产级多租户已经实现。任何外部副作用工具必须另行定义 scope、超时、取消、幂等和部署授权。
