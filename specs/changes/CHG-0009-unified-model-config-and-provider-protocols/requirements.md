---
kind: requirements
id: CHG-0009-REQUIREMENTS
status: accepted
---

## R1 — 统一模型配置

WHEN 租户创建、查询、更新或删除模型连接
THE SYSTEM SHALL 使用单一 `ModelConfig` 资源同时表达 provider adapter、API protocol、model、endpoint、非敏感配置和加密凭证。

WHEN Agent Revision 被保存
THE SYSTEM SHALL 只持久化 `model_config_id` 及允许的非敏感扩展覆盖，不持久化 provider、model 或凭证副本。

## R2 — 多租户与密钥边界

WHEN 用户访问 ModelConfig
THE SYSTEM SHALL 按 tenant 隔离 CRUD、引用检查和运行时解密；GET/PATCH 响应只能返回脱敏凭证元数据。

WHEN provider 运行
THE SYSTEM SHALL 在受信任运行时边界解密当前租户的 ModelConfig 凭证，调用结束后不写入 Agent、Run、Event、日志、prompt 或 HTML。

## R3 — 协议适配

WHEN provider manifest 声明 `openai_chat_completions`
THE SYSTEM SHALL 使用 OpenAI-compatible `/chat/completions` 请求和响应合同。

WHEN provider manifest 声明 `anthropic_messages`
THE SYSTEM SHALL 使用 Claude Messages API `/v1/messages`、`x-api-key`、`anthropic-version`、system message、tool_use/tool_result 和 usage 合同。

WHEN protocol、配置 Schema、凭证或模型配置不可用
THE SYSTEM SHALL 在保存 Agent 或启动 Run 前 fail closed，且错误不得回显凭证或完整配置值。

## R4 — 模型目录与控制台

WHEN控制台配置 ModelConfig
THE SYSTEM SHALL 从 Provider manifest 展示官方模型目录的推荐枚举，并提供自定义模型 ID 作为扩展路径。

WHEN 用户进入控制台
THE SYSTEM SHALL 在侧边栏提供独立的“凭证&模型配置”入口；Agent 表单只选择已启用的 ModelConfig。

目录证据（2026-07-31）：

- OpenAI Models: https://platform.openai.com/docs/models （GPT-5.6 Sol/Terra/Luna）
- Anthropic Models: https://docs.anthropic.com/en/docs/about-claude/models/overview （Claude Opus 5、Sonnet 5、Haiku 4.5）
- DeepSeek API: https://api-docs.deepseek.com/ （DeepSeek V3/R1 系列）
- 阿里云百炼模型列表: https://help.aliyun.com/zh/model-studio/getting-started/models （Qwen 系列）
- Moonshot API: https://platform.moonshot.cn/docs/intro （Kimi/Moonshot 系列）
- 智谱开放平台: https://open.bigmodel.cn/dev/api （GLM 系列）
- 火山方舟模型文档: https://www.volcengine.com/docs/82379/1330310 （豆包 Seed 系列）
- 腾讯混元文档: https://cloud.tencent.com/document/product/1729 （混元系列）

## R5 — 可追踪门禁

WHEN 本变更交付
THE SYSTEM SHALL 通过统一配置的加密/租户/引用/删除保护测试、OpenAI 与 Claude 请求转换测试、前端枚举和侧边栏 SSR 测试，并更新 traceability。
