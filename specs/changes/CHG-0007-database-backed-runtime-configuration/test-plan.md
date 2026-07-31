# Test plan

| 场景 | 证据 |
|---|---|
| secret 不在 GET、数据库明文、Run 输出 | `backend/tests/test_database_configuration.py::test_credentials_are_encrypted_and_tenant_scoped` |
| 多 profile 引用及运行时解析 | `backend/tests/test_database_configuration.py::test_multiple_model_profiles_and_references_are_database_backed` |
| OpenAI provider 缺少数据库 profile/credential 时 fail closed | `backend/tests/test_database_configuration.py::test_openai_profiles_require_database_credentials` |
| 被引用配置不可删除 | 同上 |
| RuntimeConfig CAS 与敏感键拒绝 | `backend/tests/test_database_configuration.py::test_runtime_config_is_versioned_and_rejects_secrets` |
| 既有 runtime/API 合同 | `python -m pytest backend/tests -q` |
| 控制台类型、规范和构建 | `npm run lint && npm run typecheck && npm test` |
