---
kind: decision-record
id: ADR-0011
status: accepted
date: 2026-08-02
supersedes: []
---

# 本地开发工作区工具

## Context

自进化 Agent 的模型和运行链路已经可用，但默认工具只有远程只读能力；Docker sandbox 又按 ADR-0010 禁止宿主挂载，因此 Agent 无法对当前仓库做真实检查和小范围进化。

## Decision

增加显式 opt-in 的 `tool.workspace`，只用于本地开发 Compose：

- 所有路径限制在部署提供的 `/workspace` root，敏感文件和 `.git` 内部不读；
- 只提供目录列出、分段读取、固定 Git 状态/差异、固定后端测试和受校验 unified patch；
- patch 写入需要 binding 的 `allow_write=true`，并拒绝删除、symlink、binary 和文件 mode 改动；
- 子进程使用无凭据最小环境、有界输出、父 Run timeout/cancel，不暴露 Docker socket；
- 默认 Agent 不挂载，生产部署不因该本地开发 override 获得 workspace mount。

## Consequences

本地 Agent 能真实检查、修改和测试仓库，解决自进化“只能回复不能改码”的缺口；但该能力仍是本地单进程边界，不能宣称实现通用 workspace sharing、RBAC、copy-on-write、租户隔离或生产级沙箱。
