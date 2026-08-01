---
kind: change-proposal
id: CHG-0028
status: in_progress
target: 0.1
date: 2026-08-01
implementation_status: in_progress
requirements:
  - VISUAL-006
---

# Restore the pre-green Agent palette

历史版本的 Agent 对话使用更鲜明的靛蓝作为主操作色。后续低饱和灰蓝和多层 CSS 覆盖
让主操作、选中态和成功态的视觉语义混在一起。本变更恢复此前会话中验证过的靛蓝体系
（主色 `#5667d8`、信息色 `#4c82c9`），同时保留 CHG-0027 的白色阅读流、Composer、
Plan、Todo、Choice 和 Trace 结构。

本变更只调整展示层 token 和覆盖规则，不改变运行事件、模型配置、密钥引用或核心合同。
