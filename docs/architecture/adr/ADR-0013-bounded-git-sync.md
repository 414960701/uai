---
kind: decision-record
id: ADR-0013
status: superseded
date: 2026-08-02
supersedes: []
superseded_by: ADR-0015
---

# ADR-0013：受限 Git 同步工具

## 背景

工具凭证已经可以通过 `credential_ref` 在运行时解析，但工作区工具只支持本地检查、
补丁和测试。自进化 Agent 若要把已验证的 UAI 改进同步到远端，还需要拉取和推送能力；
把 Git 命令、远端或 Token 直接交给模型会突破最小权限和密钥边界。

## 决策

增加显式 opt-in 的 UAI Forge `tool.git`，作为一个统一的 Git 工具提供 `status`、`diff`、
`pull`、`push` 和 `commit_and_push` 五个固定动作：

- binding 固定部署提供的绝对 `root_path`、精确 HTTPS `allowed_remote_url`、
  `allowed_branches`、`allowed_paths` 和 `credential_ref`；模型不能传入远端、分支、路径或命令。
- `pull` 只在干净工作区执行 `git pull --ff-only --no-tags`；`push` 使用明确的
  `HEAD:<current-allowed-branch>` refspec，不使用 force、删除远端分支、tag 或任意 flags。
- `commit_and_push` 只暂存 allowlist 内的变更，拒绝预先存在的 index 变更、敏感路径和默认删除；
  提交失败或敏感内容检测失败会清理 index，推送失败则保留本地提交并返回可恢复的结构化结果。
- Git Token 只由运行时私有 `ToolCredentialPort` 以 `credential_ref` 解析，短暂注入受限
  `GIT_ASKPASS` 子进程环境；Token 不进入 Agent 定义、prompt、事件、日志、结果或命令参数。
- 工具使用固定 argv、有界输出、超时和取消清理；不把 Git 工具加入新 Agent 默认工具集合。

## 后果与边界

Agent 可以在明确配置范围内完成“改码—测试—提交—推送”闭环，也可以在干净工作区先快进拉取；
它不能自动解决合并冲突、改写历史、访问任意仓库或替代生产级审批、RBAC、outbox/idempotency
和 Secret Manager。远程副作用仍受 Agent binding 的 permission、Run 预算和部署范围约束。
