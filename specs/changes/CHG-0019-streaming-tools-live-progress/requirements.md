---
kind: requirements-delta
id: CHG-0019-REQUIREMENTS
status: accepted
target: 0.1
---

# Requirements delta

## CHAT-015 — 带工具 Agent 的真实增量输出

WHEN 当前模型 Provider manifest 声明 `streaming`
THE SYSTEM SHALL keep the native stream path even when the request contains tool definitions.

Provider SHALL 在自己的协议边界中传递工具定义并聚合协议级 partial tool-call fragments；
Runtime SHALL receive only complete UAI Forge `ToolCall` values. 工具调用片段不得进入
`model.delta` payload、聊天正文、日志或 Trace 展示。

WHEN 工具调用完成且 Agent 继续请求模型生成最终回复
THE SYSTEM SHALL publish ordered `model.delta` events for that final text whenever the Provider
emits text chunks. 工具执行、预算、取消、失败和事件 sequence 语义 SHALL remain unchanged。

WHEN Provider 不声明 `streaming` 或 native stream 在尚未公开任何内容前失败
THE SYSTEM SHALL retain the existing `complete` fallback. SYSTEM SHALL NOT fabricate deltas。

## CHAT-016 — Provider-neutral stream chunk

`ModelStreamChunk` SHALL contain text, optional usage and a list of complete provider-neutral
`ToolCall` values. The core contract SHALL contain no Provider SDK, HTTP response, credential,
partial JSON buffer or raw request payload。

## THINK-006 — 自然的公开执行活动条

WHEN Agent 对话中存在公开阶段事件
THE SYSTEM SHALL show a compact live activity surface with the current/recent public stage,
safe summary and terminal state. The compact surface SHALL default to a single activity row;
ordered stage history MAY be expanded on demand。

The compact surface SHALL keep the public-summary boundary visible and SHALL NOT show raw
chain-of-thought, private reasoning blocks, complete prompts, credentials or unredacted tool
arguments. Run inspector and Trace SHALL continue to derive their detailed view from the same
Run Event stream。
