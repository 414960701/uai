---
kind: design-delta
id: CHG-0019-DESIGN
status: implemented
target: 0.1
---

# 带工具流式与公开活动条设计

## 1. 核心流式合同

`ModelStreamChunk.tool_calls` 是完整 `ToolCall` 列表。OpenAI-compatible 适配器按 tool-call
index 聚合 id、函数名和 arguments；Anthropic Messages 适配器按 content block index 聚合
tool-use id/name 与 `input_json_delta.partial_json`。两者只在流结束后把安全解析后的调用
交给核心。解析失败沿用现有安全 fallback `{"raw": ...}`，不把原始片段写入事件。

## 2. Runtime 路由

Runtime 只以 Provider manifest 的 `streaming` capability 决定是否进入 `stream()`；工具
定义不再单独禁用流式。Runtime 分别累积 text 与 complete tool calls，只有 text 触发
`model.delta`；最终 `ModelOutput` 同时携带正文和工具调用，继续进入既有工具守卫与预算链。

## 3. 聊天表现

完整 Trace 仍使用原有 `PublicReasoningPanel` 详细列表。聊天 compact 形态改成一行活动条：
左侧状态点，中间是“正在分析任务”等自然语言和一行安全摘要，右侧显示阶段位置或终态；
点击后展开无 Agent/深度/时间噪声的阶段轨迹。正文增量继续沿用 `model.delta` 事实源和同一
SSE/历史回放链路。

## 4. 安全与兼容

`RunEvent`、SSE API 路径、工具校验、Trace 关联和密钥引用均不变。无 streaming capability
的 Provider 仍走 `complete()`；已有不带工具的流式行为保持不变。未实现跨进程生成器恢复，
也不把 Provider 私有 reasoning block 转发到前端。
