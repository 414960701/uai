kind: change-proposal
id: CHG-0037
status: proposed
target: 0.1
title: Durable tool approval with waiting state and resume
---

## 背景

当前 `ToolBinding.permission == "confirm"` 的工具在运行时直接抛
`PermissionRequiredError`，Run 以 FAILED 结束。`RunManager.start` 固定把
`metrics.approved_tools` 置空。

远程 Agent 框架需要 human-in-the-loop：敏感工具调用应暂停 Run，持久化一个
Approval 资源，由用户批准或拒绝后继续执行，而不是让整个 Run 失败。

## 范围（本 change 落地）

- 持久化 `Approval` 资源（tenant 隔离、CAS 状态机、call 级一次性授权与可选的
  run 级 sticky 授权）。
- `RunStatus.WAITING_APPROVAL` 与 `approval.requested` / `approval.resolved` 事件。
- confirm 工具在进程内等待审批；批准后以一次性授权继续该工具调用；拒绝后把
  拒绝消息回填给模型，Run 继续而非失败。
- 控制面 API：列出 Run 的 approvals、按 approval id approve/reject、恢复
  WAITING_APPROVAL 的 Run（进程重启后的恢复路径）。
- 等待期间取消 Run：pending approvals 置为 revoked，Run 进入 CANCELLED。

## 非目标

- 多用户 RBAC / 签名一次性 token / 审批过期后台清扫器 / 分布式协调器。
- `waiting_input`（用户输入请求）状态；Choice 已覆盖用户有限选项选择。
- 前端审批 UI（后续 change 单独做）；本 change 只提供控制面 API 与事件。
- 跨进程 checkpoint 续跑：0.1 仍是单进程基线；进程重启后通过 `resume` 重新驱动。

## 取舍依据

公开研究（OpenAI Agents SDK HITL、LangGraph interrupt/checkpoint）表明主流实现把
审批建模为：工具声明需要审批，Run 暂停并暴露 pending 审批，按 call_id 一次性
