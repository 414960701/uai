---
kind: change-proposal
id: CHG-0025
status: in_progress
target: 0.1
date: 2026-08-01
implementation_status: in_progress
requirements:
  - VISUAL-001
  - VISUAL-002
  - VISUAL-003
  - VISUAL-004
  - VISUAL-005
---

# Calm light console palette

当前控制台虽然已有浅色覆盖，但主色仍偏灰蓝，旧的深色组件规则也散落在 Agent、运行
记录、拓扑、扩展和设置页面中，导致同一产品内出现多套视觉语言。本变更补充一轮
网站式的云白/低饱和蓝视觉收敛：统一控制台的表面层级和颜色角色，保留聊天、Trace、
Plan、Todo 与状态交互语义不变。

本变更只调整展示层：不改变运行事件、模型配置、密钥引用、权限边界或核心契约。
