---
kind: change
id: CHG-0009
status: accepted
date: 2026-07-31
---

# 统一租户模型配置与 Provider 协议

当前控制面把凭证和模型档拆成两类资源。Agent 先选择模型档，模型档再引用另一条
凭证记录；这会让一个实际可运行的模型连接跨越两组 CRUD、两次删除保护和两套前端
表单，也无法直接表达 Claude Messages API 与 OpenAI Chat Completions 的协议差异。

本变更删除旧的 `CredentialProfile`/`ModelProfile` 公共合同，改为一个租户隔离的
`ModelConfig` 资源。每条配置同时保存协议、适配器、模型、端点、非敏感参数和加密后的
凭证；Agent Revision 只保存 `model_config_id`。内置适配器增加 Anthropic Claude
Messages API，并由 Provider manifest 提供官方模型目录，控制台用枚举控件展示推荐模型。
自定义模型 ID 仍可用于尚未进入目录的模型。

本项目明确不兼容旧 API 和旧配置表；不提供旧资源的迁移或别名端点。
