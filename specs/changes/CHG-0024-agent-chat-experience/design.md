---
kind: design-delta
id: CHG-0024-DESIGN
status: in_progress
target: 0.1
---

# 设计决策

1. 桌面端默认两列：会话侧栏 + 主对话。只有当前 Run 有 Todo/Plan 时，右侧显示轻量
   Task Monitor；用户点击“查看 Trace”后切换为完整运行详情。空对话不显示空的 Inspector。
2. Assistant 回复使用平面消息流，用户输入保留轻量气泡；状态、时间和 Run 入口放在
   辅助行，避免每条回复变成厚重后台卡片。
3. 运行中公开阶段使用一行活动摘要；终态由 `PublicReasoningPanel` 收起，用户可以
   手动展开查看公开阶段，原始 reasoning 永远不进入该组件。
4. Composer 用紧凑胶囊承载思考模式和执行方式。Plan 只显示“先审阅”的状态提示，
   不把安全说明占满输入区。
5. TaskTodoList 由 provider-neutral 启发式根据动作类别生成安全的公共步骤标题，不回显
   原始输入，避免把凭证或敏感文本复制到任务监视器。
6. 窄屏只保留会话/Agent 选择条与主对话，Trace 和 Task Monitor 不强行占用首屏；Todo
   在当前消息下保留紧凑版本。
