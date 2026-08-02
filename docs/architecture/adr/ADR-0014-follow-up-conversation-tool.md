---
kind: decision-record
id: ADR-0014
status: accepted
date: 2026-08-02
supersedes: []
---

# ADR-0014：Follow-up Conversation 工具

## 背景

自进化 Agent 一轮 Run 完成后，下一轮工作不应依赖控制台人工复制输入。UAI Forge 已有统一的
`RunManager.start`、Agent revision、session 和事件合同，因此工具只需要把下一轮任务提交回
这个应用边界。

## 决策

增加显式可挂载的 `tool.conversation`：

- `input` 是下一轮对话的任务；省略 `agent_id` 时沿用当前 Agent，省略 `session_id` 时创建新的
  会话 ID；也可显式选择已存在的 Agent/revision、thinking mode 和 execution mode。
- 工具只通过私有 `RunSubmissionPort` 调用 `RunManager.start`，不访问 HTTP、SQLite 或模型供应商
  API，也不绕过常规拓扑、revision、session、permission、timeout 和 budget 校验。
- 返回新 Run 的 ID、Agent/revision、session 和状态；父 Run 可以把该工具作为最后一个动作调用，
  新 Run 作为异步 follow-up 继续执行。
- 不把该工具加入新 Agent 默认工具集合；需要连续自进化的 Agent 必须显式绑定它并在提示词中把
  “启动下一轮”作为完成阶段。

## 后果与边界

Agent 可以形成连续的多轮工作流，不必让模型伪造 HTTP 请求或等待人工创建下一轮 Run。每个新 Run
仍是独立的单进程 Run，当前 0.1 没有 durable Session、跨 Run checkpoint、outbox/idempotency
或全局 loop controller；部署者需要通过 Agent policy、scheduler 或停止 Run 控制长期运行。
