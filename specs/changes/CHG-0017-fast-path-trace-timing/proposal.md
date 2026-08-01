---
kind: change-proposal
id: CHG-0017
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - PERF-001
  - PERF-002
  - TRACE-001
---

# 快速澄清路径与 Trace 阶段耗时

天气 Agent 在缺少城市时不需要启动“父 Agent → 子 Agent → 父 Agent 汇总”的模型链路；
当前行为会把一个可以立即回答的澄清问题放大成多次远程模型等待。本变更增加一个由 Agent
标签显式声明的、非敏感的快速澄清路径，只处理已声明的地点缺失天气意图；普通任务和带有
地点的天气任务继续走既有运行时。

同时把模型、工具、委派和 Agent span 的持续时间写入完成事件，并在运行记录中投影成阶段耗时
与进行中计时。Trace 仍以 Run Event 为唯一事实源，不创建第二套 span 存储。
