---
kind: requirements-delta
id: CHG-0034-REQUIREMENTS
status: accepted
target: 0.1
---

## CFG-010 — 工具凭证资源

WHEN 操作者创建或更新工具凭证
THE SYSTEM SHALL 只在控制面边界接收一次性 secret，并在写入 SQLite 前使用部署注入的 credential master key 加密；响应、查询、事件、日志、Agent prompt 和前端持久化 SHALL 只包含 `masked_secret`、metadata 和稳定的 credential ID。

WHEN 工具凭证被更新
THE SYSTEM SHALL 使用 tenant-scoped version CAS；过期版本 SHALL 被拒绝，secret 只能通过 `replace` 或 `clear` 动作改变，不能通过普通 metadata/config 字段写入。

WHEN 工具凭证被解析
THE SYSTEM SHALL 要求同一 tenant 的 `credential_ref`、启用状态和有效密文；跨 tenant、停用、缺失或无法认证解密 SHALL fail closed，且错误不得包含 secret 或密文。

WHEN 工具凭证被删除
THE SYSTEM SHALL 拒绝删除仍被 Agent revision 的 `tools[*].config.credential_ref` 引用的资源，并返回不泄漏 secret 的冲突结果。

## CFG-011 — 控制台工具凭证页面

WHEN 控制面连接正常
THE SYSTEM SHALL 在独立的“工具凭证”页面提供创建、掩码展示、替换、清除、启用/停用和删除操作，并展示可供工具绑定使用的 credential ID；页面 SHALL 不回显原始 secret。

WHEN 操作者为外部工具配置 credential reference
THE SYSTEM SHALL 将 reference 作为工具绑定配置中的 `credential_ref` 保存，且不得把 token 复制到 Agent 定义或提示词。

## DEP-006 — 轮换与兼容

WHEN 现有 SQLite v3 数据库启动新的控制面
THE SYSTEM SHALL 通过事务执行仅增加 `tool_credentials` 表和索引的无损升级，再写入当前 schema version；既有 Agent、Run、ModelConfig 和事件数据 SHALL 保持不变。

本 change 不宣称已实现 Git push、生产级 Secret Manager、RBAC、多租户认证或通用凭证代理；部署侧必须继续注入高熵 master key 或等价 Secret Manager 引用。
