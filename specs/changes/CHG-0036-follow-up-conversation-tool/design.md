---
kind: design-delta
id: CHG-0036-DESIGN
status: in_progress
target: 0.1
---

# Design

1. `tool.conversation` 是 UAI Forge 自有 `ToolPlugin`，parameters 只包含 input、可选 Agent/revision/session、
   thinking/execution mode 和 metadata；不包含 URL、控制密钥或第三方框架对象。
2. `RunSubmissionPort` 是 `ports.py` 中的运行时 Protocol。`RunManager` 构造时通过
   `AgentRuntime.attach_run_submission_port()` 注入自身，避免 Runtime/Manager 构造循环。
3. Runtime invoke context 只把私有 `_run_submission_port` 对象传给工具；该对象不会进入 ModelMessage、
   event payload、metrics 或持久化 JSON。工具用当前 tenant 和上下文 Agent 作为默认值，创建新的 `ses_*`
   会话 ID，并在 metadata 中记录无敏感的 parent/source 标签。
4. `RunManager.start` 返回正常 queued Run；它继续执行既有 Agent target、拓扑和 active-session 校验。
   工具捕获 LookupError/ValueError/未知异常为稳定的 `conversation.*` 结构化结果，不把堆栈返回给模型。
5. 新 Agent 默认集合保持只读 Web、计算和时间能力；控制台可以显式添加 `tool.conversation`，配置为空对象。
