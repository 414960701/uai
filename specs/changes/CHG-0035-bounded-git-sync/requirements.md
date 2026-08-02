---
kind: requirements-delta
id: CHG-0035-REQUIREMENTS
status: in_progress
target: 0.1
---

## GIT-001 — 常规 Git 工具

WHEN Agent 显式绑定 `tool.git`
THE SYSTEM SHALL 要求部署提供的绝对 `root_path` 和 `credential_ref`，并可选配置 `remote_name`；
当前仓库必须存在且 remote/checkout branch 可被 Git 读取。

WHEN Agent 调用 `tool.git`
THE SYSTEM SHALL 接受 `status`、`diff`、`pull`、`push`、`commit` 和 `commit_and_push` 六个常规动作；
模型不得提供任意 Git 子命令、flags、remote、branch、pathspec、环境变量或凭据。

## GIT-002 — 常规拉取与推送

WHEN Agent 调用 `pull`
THE SYSTEM SHALL 执行固定的 `git pull --no-tags` 并返回结构化结果；Git 自身的冲突或远端失败
不得被工具伪装成成功。

WHEN Agent 调用 `push`
THE SYSTEM SHALL 使用绑定 remote 推送当前 checkout branch；不得 force push、删除远端分支、
推送 tag 或选择未配置的 remote。

## GIT-003 — 常规提交与恢复

WHEN Agent 调用 `commit` 或 `commit_and_push`
THE SYSTEM SHALL 使用 `git add --all` 暂存当前仓库变更并提交；提交消息必须是一行有界文本；
检测到 credential-like 内容时 SHALL 拒绝提交并清理暂存区，但不得引入人工审批流程。

WHEN 本地提交成功但推送失败
THE SYSTEM SHALL 保留本地 commit，返回 commit SHA、推送失败 code 和无敏感信息的有界输出，
使后续 Run 能按正常 Git 工作流重试 push。

## GIT-004 — 凭证和进程边界

WHEN `pull`、`push` 或 `commit_and_push` 需要认证
THE SYSTEM SHALL 通过运行时私有 credential port 解析同 tenant 的 `credential_ref`；缺失、
停用、跨 tenant、解密失败或 resolver 不可用 SHALL fail closed。

THE SYSTEM SHALL 不把 Token 写入 binding config、Agent prompt、事件、日志、工具结果或命令
参数；Token 只能短暂存在于认证子进程环境，并在完成、超时或取消时清理。

WHEN Git 子进程运行
THE SYSTEM SHALL 使用固定 argv、最小环境、有界 stdout/stderr、父 Run timeout 和取消清理；
工具未显式绑定时 SHALL 不显示、不创建也不执行该能力。

本 change 不宣称实现 Git 冲突自动修复、任意 Shell/Git 子命令、force push、远端删除、
RBAC、outbox/idempotency 或 Secret Manager API；它也不增加推送前审计或人工确认流程。
