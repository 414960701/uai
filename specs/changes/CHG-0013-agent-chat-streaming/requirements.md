---
kind: requirements-delta
id: CHG-0013-REQUIREMENTS
status: accepted
target: 0.1
---

# Requirements delta

## CHAT-007 — Agent 对话增量输出

WHEN 当前 Agent 的模型 Provider manifest 声明 `streaming` 且本次模型请求没有工具定义
THE SYSTEM SHALL 在同一个 Run 中按顺序发布 `model.delta` 事件，事件 payload 只包含当前文本增量和必要的非敏感序号信息；`model.started`、增量事件和 `model.completed` SHALL 共享同一条事件流。

THE SYSTEM SHALL 通过现有历史/SSE API 传递 `model.delta`，不得新增第二个实时事实源。

WHEN 前端收到 `model.delta`
THE SYSTEM SHALL 在中央聊天区追加文本，并在 Run 未完成时显示“正在输出”状态；刷新或断线重连后 SHALL 从事件历史重建已收到的增量文本。

WHEN Provider 不声明 `streaming`、工具定义存在或流式请求失败
THE SYSTEM SHALL 回退到现有 `complete` 路径，保留工具调用解析、失败和取消语义，不伪造增量输出。

流式能力 SHALL 只通过 UAI Forge 自有 `ModelStreamChunk`/`ModelProvider` 契约暴露；Provider SDK、HTTP 客户端对象和凭证不得进入核心契约、事件或前端。

## CHAT-008 — 公开执行阶段与流式状态

THE SYSTEM SHALL 在 Run Event 流中发布不含隐藏链式思维的公开阶段事件，例如“正在准备上下文”、
“正在分析任务”、“正在调用工具”、“正在整理回复”；阶段事件只允许携带阶段、状态、稳定
标识和必要的统计信息，不得携带原始思考 token、完整 prompt、凭证或 Provider 对象。

WHEN 前端收到公开阶段事件或 `model.delta`
THE SYSTEM SHALL 在对话区显示当前阶段与可见增量；终态后 SHALL 保留阶段和增量的历史证据。

## CHAT-009 — 协作拓扑交互

WHEN 用户打开“协作拓扑”
THE SYSTEM SHALL 使用 Agent 当前图数据渲染可拖拽节点和有向挂载边，并提供缩放、适配视图、
MiniMap、控件和节点选择；节点与边 SHALL 保留 Agent ID、挂载 alias、修订和并发等稳定排障信息。

拓扑视图 SHALL 不伪造不存在的节点或边；空图、无挂载和窄屏状态需要有可理解的降级呈现。

## CHAT-010 — Run 全链路 Trace 可观测

WHEN Run 产生生命周期、Agent、模型、工具、委派、阶段、预算或终态事件
THE SYSTEM SHALL 在同一条有序 Run Event 流中保留 `trace_id`、`span_id` 和可选的
`parent_span_id` 关联；事件 SHALL 继续按每个 Run 的 sequence 持久化并可由历史/SSE 回放。

运行记录页 SHALL 提供 Trace 总览、耗时/阶段/模型/工具/委派/Token 统计、可筛选可展开的
事件详情和错误定位；展示层可以从已有事件计算耗时，但不得把 Run 记录或前端临时状态当成
第二个 Trace 事实源。

Trace 与阶段数据 SHALL 遵守最小披露：不保存或展示 API Key、Secret、完整模型请求、隐藏
链式思维或未脱敏的工具参数；保留稳定 ID 以支持排障。
