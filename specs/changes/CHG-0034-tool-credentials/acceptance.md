---
kind: acceptance
id: CHG-0034-ACCEPTANCE
status: accepted
---

- [x] 工具凭证可在独立控制台页面创建、掩码展示、轮换、清除、停用和删除。
- [x] Agent 工具绑定只保存 `credential_ref`，并在历史 revision 引用时阻止删除。
- [x] secret 加密存储、tenant 隔离、CAS、v3→v4 无损迁移均有自动化证据。
- [x] 本地 Compose 已重建并以 healthy 状态提供 v4 API；页面不提供明文读取。
- [x] 文档明确该能力不等同 Git push、Secret Manager、RBAC 或生产级多租户。
