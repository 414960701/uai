---
kind: design-delta
id: CHG-0022-DESIGN
status: implemented
target: 0.1
---

# 任务监视器设计

`TaskTodoList`、`TodoItem`、`ChoicePrompt` 和 `ChoiceOption` 位于核心模型合同中，只使用
UAI Forge 自有类型。`tasks.py` 用输入长度、动作词和连接词做保守启发式判断；简单问答
不显示清单，复杂 execute Run 从“明确目标”开始进入自动清单。计划模式仍由
`ExecutionPlan` 负责审阅，不重复生成 Todo。

运行开始时写入 `todo.created` / `todo.updated`，终态写入 `todo.completed` 或 `todo.failed`。
Run 终态事件同时携带 Todo 和 Choice 快照，保证历史回放不依赖实时订阅。

模型只有在需要有限用户决策时才可输出受限的 HTML 注释 marker。后端只接受 2-8 个选项、
校验单选/多选边界并拒绝敏感文本；前端将其渲染为选择卡，Continue 先记录选择再发送一条
普通会话消息，Skip 只记录跳过。

思考区把公开阶段作为产品状态，不把原始 reasoning 当作产品内容。运行终态由父组件 key
重新挂载为收起状态，用户手动展开后不再被每次事件刷新打断。

视觉上使用浅色中性画布、冷蓝主强调色和少量状态色，右侧任务监视器包含 Todos、Artifacts
和 Skills & MCP，详细 Trace 继续作为可展开的二级信息。
