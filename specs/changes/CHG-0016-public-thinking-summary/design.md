---
kind: design-delta
id: CHG-0016-DESIGN
status: accepted
target: 0.1
---

# 公开思考摘要设计

1. 前端从已接收的 `agent.progress`、`model.started`、`model.completed`、`tool.*` 和
   `delegation.*` 事件投影 `PublicReasoningStep`；`model.delta` 只继续用于正文，不进入
   思考步骤列表。
2. 聊天消息、右侧 Run inspector 和全链路 Trace 使用同一个投影函数，避免维护第二套状态。
3. 每个摘要步骤只展示阶段名称、公开 message、模型/工具/委派的稳定标识、状态、深度和
   时间；不把 event payload 原样展示给用户。
4. 标题使用“思考过程（公开摘要）”，并明确说明不显示原始隐藏思维。计划模式继续显示
   “只生成计划，不调用工具或子 Agent”。
