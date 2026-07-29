---
kind: change-proposal
id: CHG-0005
status: implemented
target: 0.1.x
requirements:
  - DEP-002
  - SEC-006
---

# 单节点容器发布证据

## 问题

Docker、Compose、Kubernetes 和 CI 构建制品已经存在，但 `DEP-002` 仍缺可重复的
build/start/health/真实委派证据。控制后台也必须按实际证据显示状态，不能长期停留在
“待 smoke”，更不能把单节点验证扩写成可恢复多副本云集群。

## 范围

- 增加隔离、可清理的 Compose smoke 脚本。
- 构建并启动前后端镜像，验证两个容器健康和后端 doctor。
- 通过容器化 API 发起真实 bounded child 委派并校验有序事件。
- 将 smoke 接入 CI 和 Makefile。
- 更新 `DEP-002`、部署文档、追踪与控制后台状态。
- 在公开发布前消除 lockfile 中可修复的 high/critical npm advisory，并复验 Sites/容器构建。
- 裁剪 Web 运行镜像中的开发工具链，并在镜像内重复 production audit。

## 非目标

- 不实现多 worker、checkpoint、outbox、lease/fencing 或崩溃恢复。
- 不把 Sites 前端发布当作 Python Runtime 云托管证据。
- 不加入 OIDC/RBAC、TLS 终止、PostgreSQL、Redis/NATS 或生产 Secret manager。
- 不迁移到 vinext 1 beta、TypeScript 7 或 ESLint 10 等不相关的破坏性主版本。

## 实现证据

2026-07-30 的最终门禁使用已提交锁文件完成干净安装、前后端回归和隔离 Compose
smoke。Web 运行镜像裁剪后审计 192 个 production package 为 0 vulnerabilities；
bounded delegation Run `run_f01ba3ea036e44d1` 成功并产生 sequence 1–17 的连续事件。
完整证据与仍接受的开发工具链风险记录在 [acceptance.md](acceptance.md)。
