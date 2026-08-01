---
kind: design-delta
id: CHG-0021-DESIGN
status: implemented
target: 0.1
---

# 计划审阅设计

## 领域合同

`ExecutionPlan`、`PlanStep`、`PlanStatus` 和 `PlanStepStatus` 位于
`backend/src/uai_forge/models.py`，只使用 UAI Forge 自有类型。当前单进程基线把计划嵌入
`RunRecord.plan`，这样历史 Run、SSE 终态和 SQLite JSON 可以同时回放；后续 durable plan
资源可以在不改变前端语义的情况下迁移到独立表。

计划状态为 `proposed`、`needs_revision`、`approved`、`executing`、`completed`、`failed`、
`rejected` 和 `cancelled`。步骤状态独立记录待确认、批准、运行中、完成、失败或跳过。

## 运行流程

1. Runtime 在 plan 模式添加只读规划指令，完全不实例化工具和子 Agent，并要求模型输出
   目标、假设、步骤和风险等公开结构。`plans.py` 将结构化 Markdown 或普通文本安全降级
   为 `ExecutionPlan`，缺少外部事实时保留为假设/风险。
2. RunManager 将计划和 `plan.proposed` 事件写入完成 Run。`run.completed` 同时携带计划
   摘要，保证流式客户端在未再次 fetch 时也能得到计划卡片。
3. `PATCH /api/v1/runs/{run_id}/plan` 以 expected version 进行编辑；保存后版本递增并变成
   `needs_revision`。`POST .../plan/reject` 只结束计划，不创建执行。
4. `POST .../plan/approve` 在批准前校验计划状态/版本，服务端将计划置为 executing，再
   创建新的 execute Run。新 Run 的 metrics 只记录 `source_plan_id`、`source_plan_run_id`
   和 `source_plan_version`，并以 `agent_revision` 固定原始根版本。
5. 执行 Run 的成功、失败或取消通过计划事件回写源 Run 的计划状态和步骤状态。执行仍沿用
   现有预算、超时、取消、SSE 和 Trace；本变更不扩展成恢复型状态机。

## 前端交互

聊天结果和运行详情都渲染 `PlanCard`，显示标题、版本、目标、步骤、假设、风险和状态。
待审阅计划提供修改、批准并执行、暂不执行；修改使用表单而不是让用户编辑不透明 JSON。
批准后页面切换到新执行 Run，源计划保留为同一 Session 的审阅历史。事件时间线使用中文
名称，同时保留稳定的事件 code。

## 安全与隐私

计划只展示模型公开输出转换出的摘要；前端和 trace scrubber 不展示隐藏思维、provider
headers、凭据或原始工具参数。计划模式的工具调用保护仍由 Runtime 兜底，即使 provider
意外返回 tool call 也不会执行。
