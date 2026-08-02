---
kind: decision-record
id: ADR-0015
status: accepted
date: 2026-08-02
supersedes:
  - ADR-0013
---

# ADR-0015：常规 Git 工作流工具

## 背景

UAI Forge 已有工具凭证资源和 `credential_ref` 运行时解析能力。自进化 Agent 需要把已完成的
代码修改提交到当前仓库并同步远端，也需要能够在工作前拉取最新代码。此前的设计把 remote、
branch 和 path 固定成 allowlist，并增加了提交内容审计；这不是用户需要的常规 Git 工具体验。

## 决策

增加显式挂载的自有 `tool.git`，提供常规的 `status`、`diff`、`pull`、`commit`、`push` 和
`commit_and_push` 动作：

- binding 配置仓库 `root_path`、`credential_ref` 和可选 `remote_name`；工具读取该仓库当前
  remote 与 checkout branch，不要求额外的远端 URL、分支或路径 allowlist。
- `pull` 执行普通 `git pull --no-tags`；`push` 推送当前 checkout branch；`commit` 执行
  `git add --all` 后提交当前工作区；`commit_and_push` 依次执行 commit 和 push。
- 模型只能选择上述结构化动作和提交消息，不能传入任意 Git 子命令、flags、remote、branch、
  pathspec、环境变量或凭据；force push、远端删除和 tag 推送不属于该工具合同。
- 不增加推送前审计或人工确认门槛。提交仍关闭仓库 hook，避免 Agent 进程执行仓库内任意 hook；
  这不是业务审批流程。为遵守密钥边界，检测到 credential-like 内容仍会拒绝提交并清理暂存区，
  这也不是人工审计。
- Git Token 只由私有 `ToolCredentialPort` 按 `credential_ref` 解析，短暂注入认证子进程环境；
  Token 不进入 Agent 定义、prompt、事件、日志、工具结果或命令参数。

## 后果与边界

Agent 可以在绑定仓库内完成普通的拉取—修改—提交—推送闭环，不需要额外 allowlist 或人工
批准。工具仍不是任意 Git shell，也不提供冲突自动解决、force push、远端删除、outbox/
idempotency、RBAC 或生产级 Secret Manager；新 Agent 默认仍不自动挂载外部副作用工具。
