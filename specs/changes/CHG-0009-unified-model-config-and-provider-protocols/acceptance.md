---
kind: acceptance
id: CHG-0009-ACCEPTANCE
status: accepted
---

- [x] 生产 API 只提供 `/api/v1/model-configs`，不存在 `/credentials` 和 `/model-profiles`。
- [x] 新配置响应不包含 secret，SQLite `model_configs.secret_ciphertext` 不包含明文。
- [x] Agent JSON 只有 `model_config_id`，运行时按 tenant 解引用。
- [x] Provider catalog 同时包含 OpenAI-compatible 与 Anthropic Messages，且每个 manifest 有推荐模型枚举。
- [x] 控制台侧边栏含“凭证&模型配置”，Agent 表单不再出现凭证/模型 JSON 输入。
- [x] 后端、前端和容器门禁全部通过。
