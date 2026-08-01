---
kind: change-proposal
id: CHG-0027
status: in_progress
target: 0.1
date: 2026-08-01
implementation_status: in_progress
requirements:
  - CHAT-027
  - CHAT-028
  - CHAT-029
  - CHAT-030
  - CHAT-031
---

# Reference-aligned Agent conversation surface

现有 Agent 对话已经具备流式事件、公开阶段、Plan、Todo、Choice 和 Trace 合同，但默认
表面仍然像运行后台：消息、阶段和任务都被厚重卡片包住，用户需要在多个相似入口之间
判断下一步。参考用户提供的 Agent 截图以及 Replit、Claude Code、Cursor、Kiro、Deep
Research 和 Codex 的公开交互模式，本变更把聊天重新收敛为一条可阅读、可介入的主路径。

本变更只调整聊天展示层和选择交互，不改变 Run/Event 事实来源、Plan 安全边界、Todo
复杂度判断、Choice marker 校验或 Trace 数据合同。
