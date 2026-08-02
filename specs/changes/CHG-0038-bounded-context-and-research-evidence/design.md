---
kind: design-delta
id: CHG-0038-DESIGN
status: in_progress
target: 0.1
---

# Design

1. `AgentRuntime._serialize_tool_result_for_model` 是普通工具和委派结果共同使用的边界。
   它只产生有界字符串；工具仍可通过自己的 offset/limit 或分页合同取得剩余内容。
2. `AgentRuntime._compact_model_history` 使用字符和消息两个防线。初始 system contract
   与当前 task message 固定保留，旧 memory 可丢弃，工具调用按完整轮次保留/丢弃；压缩后
   的 task/marker 成为后续调用的固定前缀，避免重复注入。
3. 压缩事件使用现有 `EventType.AGENT_PROGRESS`，阶段为 `context_compacted`，只包含
   dropped/retained message 数和压缩前后字符数等安全度量。
4. Runtime 对工具名称和规范化参数计算进程内不可逆签名；同一签名重复到达防线时发出
   `repeated_tool_call` 事件并追加一次模型可见的去重提示。它是行为反馈而不是固定步数
   或研究次数限制，正常的不同路径调用不受影响。
5. `TokenUsage.cached_input_tokens` 和 `cache_creation_input_tokens` 继续由 Provider
   适配器映射并显示；Runtime 仍以 `total_tokens` 记账，不用缓存字段放宽执行策略。
6. `docs/research/README.md` 作为研究索引和格式合同。Agent 的研究任务先读取它和相关
   笔记，把增量来源与决策追加为 Markdown，再通过普通 workspace/git 工具完成提交和
   推送；这不是另一个供应商知识库或隐式记忆系统。
