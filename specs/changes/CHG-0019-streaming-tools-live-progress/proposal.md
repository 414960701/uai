---
kind: change-proposal
id: CHG-0019
status: specified
target: 0.1
date: 2026-08-01
implementation_status: in_progress
supersedes:
  - CHG-0013 tool-request streaming exception
  - CHG-0018 compact reasoning surface
requirements:
  - CHAT-015
  - CHAT-016
  - THINK-006
---

# 带工具的真实流式与自然公开进度

最近一次真实 Run 暴露出两个问题：Agent 只要配置了工具就被 Runtime 强制切到完整响应，
导致没有 `model.delta`；同时聊天 compact 视图把公开阶段渲染成固定清单，像诊断表而不像
对话中的实时活动。

本变更让声明 `streaming` 的 Provider 在带工具请求中继续使用 SSE。Provider 在边界内
聚合工具调用片段，再通过 UAI Forge 自有的 `ModelStreamChunk` 交给 Runtime；Runtime 只
把正文增量发布为 `model.delta`，工具调用继续走既有校验、预算、执行和 Trace 链路。

聊天 compact 视图改为当前活动条，默认只显示“正在做什么”和公开摘要；点击后才查看简化
的阶段轨迹。运行详情和 Trace 继续保留完整的可审阅事件，不展示隐藏 reasoning 原文。
