---
kind: requirements-delta
id: CHG-0005-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### DEP-002A — 可重复单节点启动

WHEN 发布门禁在支持 Docker Engine 与 Compose 的环境执行
THE SYSTEM SHALL 从版本化 Dockerfile 构建 Web 与 Python Runtime 镜像，以单副本启动，
使用独立 SQLite volume，并等待两个部署单元通过健康检查。

### DEP-002B — 容器内配置与 provider 注册检查

WHEN 单节点容器栈健康
THE SYSTEM SHALL 通过公开 HTTP API 验证新数据库不包含 Agent、Instance、凭据、模型档或
运行配置，并验证 provider 注册表只包含生产 `openai_compatible` 适配器。

### DEP-002C — 隔离、清理与准确声明

WHEN smoke 成功或失败
THE SYSTEM SHALL 只清理本次测试命名的容器、网络和 volume，不影响开发者已有栈。

WHEN 控制后台或文档呈现部署成熟度
THE SYSTEM SHALL 把已验证的单节点容器与仍为规划的可恢复云集群分开，不得声称多副本恢复。

### SEC-006A — 公开发布依赖基线

WHEN JavaScript/TypeScript 控制后台准备公开发布
THE SYSTEM SHALL 使用锁定且通过完整 build/test 的依赖图，并让
`npm audit --omit=dev --audit-level=high` 对生产依赖返回零 high/critical advisory；
完整开发依赖 audit SHALL 被审查并记录剩余范围，修复不得静默升级到未验收的破坏性主版本。

WHEN 构建公开发布的 Web 运行镜像
THE SYSTEM SHALL 裁剪仅构建/开发依赖，并在镜像内对 production graph 重复执行相同
audit 门禁。
