---
kind: adr
id: ADR-0007
status: accepted
date: 2026-07-31
supersedes: ADR-0006
---

# ADR-0007：统一租户模型配置并以协议适配器承载 Provider

## 背景

ADR-0006 将凭证和模型拆成 `CredentialProfile` 与 `ModelProfile`。随着 Claude Messages
API 加入，拆分会让端点、协议、模型和密钥散落在多条记录中；Agent 的真实依赖也无法在
一处被复制、停用和审计。

## 决定

- 删除旧的 CredentialProfile/ModelProfile 公共合同、API 和仓储边界；采用单一、tenant-scoped
  `ModelConfig` 资源。
- `ModelConfig` 自带加密 secret、provider adapter、派生的 api protocol、model、endpoint
  和非敏感 config。Agent Revision 只引用 `model_config_id`。
- Provider manifest 声明 `api_protocol`、是否需要凭证和官方模型目录；协议适配器只在边界
  使用第三方 HTTP 合同，内核继续只看 UAI Forge `ModelMessage`/`ModelOutput`。
- 首批生产适配器是 `openai_compatible`（Chat Completions）和 `anthropic_messages`
  （Claude Messages）。未知协议、无效配置、无效凭证和跨租户引用 fail closed。
- 控制台将统一资源放到独立的“凭证&模型配置”侧边栏，Agent 编辑器只选择已启用配置。
- 官方模型目录是可更新的 manifest 元数据；UI 同时允许自定义模型 ID，不把目录误称为
  运行时模型发现。

## 结果

- 一个配置即一个可运行连接，减少误配和删除竞态。
- 增加协议适配器时只需扩展 manifest/adapter/TCK，不污染核心消息合同。
- 旧配置不迁移；部署前需要按新 API 重建配置。单进程 SQLite、多租户认证和 Secret
  Manager 仍遵循当前 0.1.x 的既有边界。
