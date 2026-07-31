---
kind: test-plan
id: CHG-0009-TEST-PLAN
status: accepted
---

| 风险 | 证据 |
|---|---|
| Secret 泄露或跨租户读取 | `test_model_configs_are_encrypted_and_tenant_scoped` |
| Agent 选择不存在/停用配置 | `test_agents_require_enabled_model_config` |
| 删除仍被引用的配置 | `test_model_config_delete_is_guarded_by_agent_revisions` |
| OpenAI 请求合同回归 | `test_openai_compatible_provider_maps_core_request` |
| Claude Messages 请求/响应合同回归 | `test_anthropic_messages_provider_maps_tools_and_usage` |
| 官方目录和 protocol manifest 可枚举 | `test_provider_manifests_expose_model_catalog` |
| 前端独立入口和 Agent 只选择配置 | `tests/rendered-html.test.mjs` |
