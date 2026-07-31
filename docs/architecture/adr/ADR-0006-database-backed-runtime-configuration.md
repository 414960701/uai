---
kind: adr
id: ADR-0006
status: accepted
date: 2026-07-31
---

# ADR-0006：数据库作为运行时业务配置事实源

## 背景

单进程基线原先把 OpenAI-compatible provider 的 AK 解析为进程环境变量，控制台还保留
本地演示 Agent、实例和运行数据。这个形态无法安全支持多租户、多 AK、多模型配置和多
Agent 实例，也会让页面展示与实际控制面产生分叉。

## 决策

- SQLite（以及未来兼容的持久化适配器）是租户业务配置的事实源：Agent/Revision、
  Instance、CredentialProfile、ModelProfile、RuntimeConfig、插件绑定配置和运行记录均
  通过仓储访问。
- CredentialProfile 只向控制 API 返回脱敏元数据。secret 在写入数据库前使用启动时注入的
  master key 加密；master key 是 bootstrap/Secret Manager 引用，不进入数据库、事件、
  日志、prompt、Trace 或浏览器持久化。
- Agent 的 ModelBinding 只引用 `profile_id`。运行时按 tenant 读取 ModelProfile，再
  解引用启用的 CredentialProfile，构造只存在于当前调用的 provider binding；运行完成后
  不保存该明文。
- RuntimeConfig 使用带版本的 JSON 值和 CAS 更新，且拒绝递归敏感键。它承载默认 profile、
  UI 和非敏感策略开关；数据库连接、监听地址、CORS、控制面认证和加密主密钥仍是启动前
  必须知道的 bootstrap 配置。
- 控制台连接失败时显示空状态，不生成或写回本地业务配置。多 AK、多模型和多 Agent 由
  API/数据库记录支持，前端只提交一次性 secret 并展示 mask。

## 取舍与边界

当前实现是单进程 SQLite 基线，不宣称分布式恢复、生产级多租户、RBAC 或插件沙箱。默认
开发 master key 仅用于本地/测试；部署必须显式配置高熵 `UAI_FORGE_CREDENTIAL_MASTER_KEY`
或由 Secret Manager 注入等价值。未来 PostgreSQL 适配器必须保持相同的非泄漏合同。

## 影响

- 新增 credential/model/runtime 配置表、脱敏 API 和 profile 引用字段；删除被引用的 profile
  或 credential 会 fail closed。
- 不保留旧的 `api_key_env` 或环境变量取 AK 路径；已有旧 Agent 必须迁移到
  CredentialProfile/ModelProfile 并更新 Agent revision。
- 运行事件继续只记录 provider/model/profile 元数据，不记录 secret。
