---
kind: change-proposal
id: CHG-0024
status: in_progress
target: 0.1
date: 2026-08-01
implementation_status: in_progress
requirements:
  - CHAT-020
  - CHAT-021
  - CHAT-022
  - CHAT-023
  - CHAT-024
---

# Chat-first Agent experience

当前 Agent 对话把聊天、公开阶段、Todo、Plan 和全链路 Trace 同时铺在同一层，导致
用户无法分辨“我该继续看什么”和“系统内部发生了什么”。参考 Claude Agent View、
OpenAI Deep Research、Codex CLI 以及提供的 Agent 界面截图，本变更把对话重新定义为
主路径：回答优先、运行中的任务进度按需出现、详细 Trace 由明确动作打开。

本变更只调整展示层和复杂任务摘要，不改变 Run/Event 的事实来源，也不把隐藏思考内容
变成产品输出；计划模式的安全边界和批准后创建执行 Run 继续遵循 CHG-0021。
