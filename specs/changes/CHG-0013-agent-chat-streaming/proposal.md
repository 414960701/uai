---
kind: change-proposal
id: CHG-0013
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - CHAT-007
  - CHAT-008
  - CHAT-009
  - CHAT-010
---

# Agent 对话流式输出

当前 Agent 对话只通过 SSE 接收 Run 生命周期和事件，模型正文要到
`run.completed` 才进入 `RunRecord.output`，用户无法看到模型正在生成的内容。

本变更为 UAI Forge 自有 Provider 契约增加可选的文本流能力，并把增量映射为
受治理的 `model.delta` RunEvent。具备 `streaming` 能力且没有工具定义的模型请求
逐段输出；工具调用或不支持流式的 Provider 继续走现有完整响应路径。

同时补充不暴露隐藏链式思维的公开执行阶段事件、可追踪的 trace/span 关联，以及
运行记录里的 Trace 观察视图。协作拓扑使用 React Flow 展示真实节点、边、缩放、拖拽、
MiniMap 与适配视图；这些均复用现有 Agent/Run/Event 合同，不创建第二套执行事实源。

不引入新的 Session 事实源，不把 Provider 对象泄漏到核心，不改变密钥保存方式，
也不声称具备分布式流恢复。
