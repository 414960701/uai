---
kind: acceptance
id: CHG-0005-ACCEPTANCE
status: passed
---

# Acceptance

- [x] 两个生产镜像从版本化 Dockerfile 构建成功。
- [x] 后端与前端容器健康，容器内 doctor 通过。
- [x] 新数据库启动成功，未自动生成 Agent、凭据、模型档或运行记录。
- [x] smoke 对开发者现有 Compose 资源无破坏性影响且完成清理。
- [x] UI、current spec 与追踪共同反映单节点已验证、分布式仍规划。
- [x] production-only npm high/critical audit 为零，完整开发链 audit 已审查并记录。
- [x] 后端、前端、合同与容器门禁全部通过。

## 验收证据（2026-07-30）

- 后端：`65 passed in 3.33s`；compileall 与 pip check 通过。
- 前端：`npm ci`、`npm ls --all`、production-only audit、lint、typecheck、
  production build 与 3 项 Node 测试通过。
- 依赖：主机与裁剪后的 Web 运行镜像 production audit 均为 0 vulnerabilities；
  镜像构建审计 192 个 production package，运行镜像不存在 ESLint/Drizzle Kit。
- 完整开发链 audit：9 high、4 moderate、0 critical。high 来自 ESLint 9 依赖链的
  `minimatch`/`brace-expansion` 及其影响传播；moderate 来自 Drizzle Kit 的旧
  `esbuild` loader。它们均属于构建/开发工具且已从运行镜像裁剪。npm 建议的自动修复
  会降级 eslint-config-next、跨主版本升级 ESLint 或降级 Drizzle Kit，因此未在本
  变更中未经兼容验收强制执行。
- 合同：9 个 JSON、18 个 YAML（21 documents）均可解析；34 份 change Markdown
  frontmatter/ID 与 9 份 change YAML 的 `change_id` 一致。
- 容器：doctor 为 `status=ok`、0 Agents、11 Plugins、provider 仅为
  `openai_compatible`、0 plugin errors；控制 API 返回空的 Agent、Instance、凭据、模型档
  和运行配置集合。
- 隔离与清理：预先存在的同名 volume 被 fail-closed 拒绝且保持完好；host ports
  仅绑定 `127.0.0.1`；smoke 的两个容器、Compose network、SQLite volume 和两个
  临时 image tag 均已删除。

接受边界：完整开发工具链仍有上述非运行时 advisory，GitHub 可能显示 dev dependency
告警；Kubernetes 单副本清单尚未做集群实测。本证据不覆盖公网 TLS、OIDC/RBAC、备份
恢复、多 worker、checkpoint/outbox/lease 或故障恢复。
