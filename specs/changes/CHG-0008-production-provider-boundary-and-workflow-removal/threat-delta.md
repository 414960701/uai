---
kind: threat-delta
id: CHG-0008-THREAT
status: accepted
---

# Threat delta

| 威胁 | 处置 |
|---|---|
| 空数据库被误认为已有可运行 Agent | 启动不 seed，doctor 和控制 API 明确返回空集合 |
| 测试 provider 被生产调用 | 生产 registry 仅注册 `openai_compatible`；测试 provider 只在测试边界显式注册 |
| 断线页面伪造运行、配置或健康数据 | disconnected 状态清空业务集合且不发起本地 fallback 请求 |
| 删除 workflow 导致发布检查消失 | Makefile、前后端命令和容器 smoke 作为版本化显式门禁 |
