---
kind: change-proposal
id: CHG-0007
status: implemented
target: 0.1.x
requirements:
  - CFG-001
  - CFG-002
  - SEC-008
  - CFG-003
---

# 数据库驱动的运行时配置与多凭据

## 问题

provider AK 依赖环境变量，控制台还会在 API 不可用时回退到本地演示数据；两者都不适合
多 AK、多 Agent、多模型配置及可审计的云/本地运行。

## 范围

- 增加加密 CredentialProfile、ModelProfile、版本化 RuntimeConfig 的 SQLite 持久化和
  租户隔离 API。
- 将 Agent ModelBinding 扩展为 profile 引用，运行时按数据库解析 provider 与凭据。
- 控制台从 API 加载真实配置，提供多凭据、多模型档和非敏感运行配置管理；断线不创建
  本地业务数据。
- 增加安全、CAS、引用完整性和运行时解析测试，并记录迁移/兼容边界。

## 非目标

- 不把数据库连接、监听端口、CORS、控制面认证或加密 master key 放入数据库；它们是
  启动 bootstrap 配置。
- 不宣称分布式恢复、完整 RBAC、生产级多租户或插件沙箱。
- 不把 AgentScope、LangGraph、AutoGen 或 provider SDK 类型泄漏到核心契约。
