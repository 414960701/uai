---
kind: change-proposal
id: CHG-0018
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - CHAT-011
  - CHAT-012
  - CHAT-013
  - CHAT-014
---

# 对话与控制台表面重做

当前 Agent 回复把正文、状态、公开思考摘要和 Run 诊断都放进同一个高对比度卡片，
造成视觉嵌套、阅读方向不连续，也让流式输出看起来像不断重绘的面板。本变更只调整
前端消息表面和全局控制台 chrome，不改变 Run、事件、Trace 或安全披露边界。

参考 ChatGPT、Claude、Cursor 和 Vercel AI SDK 的共同模式：用户消息使用轻量气泡，
助手回复使用无框正文流；执行过程作为可折叠活动条，底层 Run/Trace 通过明确操作进入。
同时把安全的基础 Markdown 投影到正文，避免把模型的格式标记直接展示给用户。
