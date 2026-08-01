---
kind: change-proposal
id: CHG-0016
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - THINK-004
  - THINK-005
---

# 公开思考摘要

用户需要知道 Agent 当前如何推进任务，但原始隐藏 chain-of-thought 不应进入事件、日志或
前端。此变更在聊天、Run inspector 和运行记录 Trace 中增加“思考过程”公开摘要视图，复用
已有的阶段、模型、工具和委派事件，显示安全的阶段标题、状态、稳定 ID 与非敏感统计。

公开摘要不是原始推理转发，也不承诺展示模型内部每一步思维；Provider 的 reasoning/thinking
block 继续保持边界内并被丢弃。
