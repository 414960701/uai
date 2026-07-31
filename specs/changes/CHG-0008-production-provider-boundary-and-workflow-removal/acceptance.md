---
kind: acceptance
id: CHG-0008-ACCEPTANCE
status: passed
---

# Acceptance

- [x] 产品 provider catalog 只包含 `openai_compatible`。
- [x] 空数据库启动不生成 Agent、Instance、凭据、模型档、运行配置或事件。
- [x] 前端断线显示 disconnected 空状态，不生成本地业务数据。
- [x] `.github/workflows` 已删除，构建不依赖托管平台 workflow。
- [x] 测试 provider 只存在于 `backend/tests`，不进入生产 registry。
- [x] 后端、前端、shell 与容器 smoke 门禁通过。
