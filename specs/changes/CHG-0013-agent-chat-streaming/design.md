---
kind: design-delta
id: CHG-0013-DESIGN
status: implemented
target: 0.1
---

# Agent 对话流式输出设计

## 1. Provider 边界

`ports.py` 增加由 UAI Forge 拥有的 `ModelStreamChunk` 和可选的
`ModelProvider.stream(request)`。默认实现调用既有 `complete` 并只产出一个完整块，
保证第三方 Provider 兼容；只有 manifest 包含 `streaming` 的适配器才被运行时用于
真正的文本流。

## 2. 运行时事件

无工具的流式模型请求在 `model.started` 后逐块发布
`model.delta`，payload 为 `{text: string}`；运行时聚合所有块形成最终
`ModelOutput.content`，继续执行现有 middleware、记忆、预算和终态事件。工具定义
存在时使用 `complete`，避免部分 tool-call JSON 被当成正文。

## 3. 前端投影

聊天工作区从当前 Run 的 `model.delta` 事件重建 `stream.output`，运行中的消息显示
已收到文本和轻量光标；事件详情隐藏逐字增量，但保留 `seq`、模型和工具事件。历史
回放与 SSE 重连沿用现有 sequence 去重逻辑。

## 4. 边界与回退

OpenAI-compatible 和 Anthropic 内置适配器解析各自的 SSE 传输；连接中断直接沿用
现有 Run 失败/取消与前端重连路径。流式失败不再发出伪造 delta，Run 由现有错误
路径终止。0.1.x 不承诺跨进程或重启后的生成器恢复。

## 5. 公开阶段（安全替代思考展示）

运行时只发布可审计的阶段摘要，不发布隐藏链式思维。阶段使用稳定枚举和中文展示映射：

```text
preparing  → 正在准备上下文
analyzing  → 正在分析任务
generating → 正在生成回答
tool_call  → 正在调用工具
delegating → 正在委派子 Agent
composing  → 正在整理回复
completed  → 已完成
failed     → 执行失败
```

阶段事件与模型、工具、委派事件共享同一 Run Event 序列；前端只投影最新公开阶段和已收到的
正文增量。

## 6. Trace 关联与运行记录

每个 Run 生成一个不含秘密的 `trace_id`。根 Agent、子 Agent/委派调用共享该 trace，分别使用
`span_id` 和 `parent_span_id` 建立调用树；同一个 span 上的模型、工具和阶段事件复用 span ID。
`RunEvent` 顶层只增加可选关联字段，因此旧事件仍可回放。运行记录页从有序事件派生 span
列表、时序瀑布、统计卡和展开详情，事件历史仍是唯一事实源。

## 7. 协作拓扑

协作拓扑使用 `@xyflow/react`，将当前 root Agent 和其挂载的 `ChildMount` 映射为节点与有向边。
React Flow 只负责交互渲染和本地布局，不写回 Agent 图；节点点击沿用现有 Agent 详情路由。
