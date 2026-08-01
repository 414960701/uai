---
kind: change-proposal
id: CHG-0012
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - CHAT-001
  - CHAT-002
  - CHAT-003
  - CHAT-004
  - CHAT-005
  - CHAT-006
---

# Agent 对话工作区与中文扩展目录

## 背景

当前控制面已经可以创建 Agent、配置模型、提交 Run 并消费持久事件，但用户需要在 Agent 列表、
运行记录和工具目录之间跳转，缺少一个围绕“持续与 Agent 对话”的独立工作区。插件 manifest 的
稳定 ID 也直接暴露为英文标题，增加了中文用户的理解成本。

## 目标

- 增加独立的“Agent 对话”导航项和三段式工作区。
- 复用 `POST /runs`、`GET /runs/{id}`、事件历史和 SSE，不创建第二套聊天执行状态源。
- 以现有 `session_id` 聚合会话；通过 URL 恢复当前运行，不声称 0.1.x 已有持久 Session 资源。
- 将工具、记忆、中间件和内置扩展以中文名称/描述展示，保留英文 ID 用于配置和排障。
- 让对话区在运行中、失败、取消、断线重连和工具调用时保持可理解、可访问、可恢复。

## 非目标

- 不新增 Session 数据库表、消息数据库或独立聊天 API。
- 不把 API Key、Secret、模型凭证或工具原始敏感配置写入 URL、localStorage、事件或 HTML。
- 不把单进程 Run/SSE 提升为分布式恢复、完整审批、生产级身份或多租户能力。
- 不把工具展示名的本地化变更误认为 manifest 合同或稳定 ID 变更。
