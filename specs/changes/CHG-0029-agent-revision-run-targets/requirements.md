---
kind: requirements-delta
id: CHG-0029-REQUIREMENTS
status: accepted
target: 0.1
---

### RUN-010 — Agent revision 是唯一根运行选择

WHEN 操作者发起一个 Run
THE SYSTEM SHALL 要求一个 `agent_id`，并允许一个可选的 `agent_revision`。

WHEN `agent_revision` 缺失
THE SYSTEM SHALL 在 Run 提交时解析该 Agent 的 `latest` 标签所指向的 revision，并把实际
revision 固定写入 Run 和 `run.started`；`latest` 不得通过取最大 revision 推导。

WHEN `agent_revision` 存在但不存在、被禁用或拓扑无效
THE SYSTEM SHALL 在持久化 Run 前拒绝请求，不创建伪造或半有效 Run。

WHEN Agent 回滚到历史 revision
THE SYSTEM SHALL 只移动 Agent 的 `latest` 指针，不删除或复用历史 revision；后续继续
发布 SHALL 分配新的递增 revision。

### UI-006 — 直接运行 Agent 与可选版本

WHEN 操作者打开“发起运行”
THE SYSTEM SHALL 只展示 Agent 作为运行目标，并提供“最新版本（默认）”和该 Agent
已有 revision 的选择。

THE SYSTEM SHALL 不再展示或要求创建、启停、环境标签、容量或 Instance override；
Agent 的创建、编辑发布和子 Agent mount revision 继续可用。子 Agent mount 的 revision
为空时 SHALL 跟随该子 Agent 的 `latest`，显式 revision 才固定历史版本。
