---
kind: change-proposal
id: CHG-0030
status: in_progress
target: 0.1
date: 2026-08-02
implementation_status: in_progress
requirements:
  - EXT-008
  - UI-007
  - CFG-008
---

# 远程 Agent 基础工具与首用默认值

远程 Agent 的首个可用闭环通常需要公开网页检索、页面正文访问、公开结构化数据、简单计算和时间查询。
当前控制面只有计算器、回声和 UTC 工具，且新建 Agent 的执行预算偏紧，用户需要先手动
拼装能力和放大预算才能处理稍复杂的研究任务。

本变更增加四个只读、受边界约束的内置 Web 工具，并让新建 Agent 默认挂载 Web 搜索、
网页访问、公开 JSON、RSS/Atom、计算器和 UTC 时间。网页工具不执行 JavaScript、不提交表单、不访问本机/私网，
所有外部内容都标记为不可信参考资料。默认预算同步调整为能覆盖正常的多步远程任务；
显式传入空工具列表仍保持最小权限语义。

全网资料调研结论记录在 `docs/research/remote-agent-tool-baseline-2026-08.md`：文件搜索、
代码执行、浏览器/计算机控制、文件/PDF、协作和业务系统连接都很常见，但它们涉及更高的
写权限、沙箱或身份边界，不随本变更默认开启。
