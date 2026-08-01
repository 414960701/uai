---
kind: requirements-delta
id: CHG-0012-REQUIREMENTS
status: implemented
target: 0.1
---

# Requirements delta

## CHAT-001 — 独立 Agent 对话入口

WHEN 用户打开控制台并选择“Agent 对话”
THE SYSTEM SHALL 显示独立的会话侧栏、中央消息区和可收起运行详情区；该工作区 SHALL 不要求用户先进入运行记录页。

## CHAT-002 — 基于现有 Run 的会话聚合

WHEN 控制面返回 Run 列表
THE SYSTEM SHALL 按现有 `session_id` 聚合会话，显示最近输入、Agent 和状态，并允许创建一个新的客户端会话 ID。

THE SYSTEM SHALL 将当前运行资源写入 URL，以便刷新和浏览器前进/后退恢复；0.1.x 不得把客户端聚合描述为持久 Session 资源。

## CHAT-003 — Agent 对话发送

WHEN 用户选择可运行 Agent 并发送非空消息
THE SYSTEM SHALL 调用现有 Run API，传递选定的 `agent_id`、输入和会话 `session_id`，立即显示用户消息与运行中状态。

WHEN Run 进入终态
THE SYSTEM SHALL 只使用服务器 Run 和事件结果显示 Agent 回复、失败或取消；前端不得伪造终态。

## CHAT-004 — 可观察的运行过程

WHEN 当前对话存在 Run
THE SYSTEM SHALL 通过事件历史和 SSE sequence 读取并去重事件，展示模型、工具、委派、预算和终态事件；工具过程 SHALL 支持折叠，并同时显示中文名称与英文 ID。

WHEN SSE 中断
THE SYSTEM SHALL 从最后确认的 sequence 重连，并在重连失败时进入有界降级状态；轮询不得成为未说明的第二个实时事实源。

## CHAT-005 — 中文展示与稳定 ID

WHEN UI 展示 Plugin、工具、记忆、中间件或事件类型
THE SYSTEM SHALL 优先展示中文名称和中文描述；稳定 plugin ID、model ID、event type 和代码字段 SHALL 保留原始英文值，并可在详情中复制/识别。

## CHAT-006 — 可访问与安全边界

WHEN 用户使用键盘、窄屏或浏览器刷新操作对话
THE SYSTEM SHALL 保持发送、选择 Agent、展开运行详情、取消运行和错误反馈可操作；焦点状态、`aria-expanded`、`aria-live` 和 reduced-motion SHALL 得到支持。

对话 UI SHALL 不持久化或回显任何 Secret、控制面密钥或模型凭证。
