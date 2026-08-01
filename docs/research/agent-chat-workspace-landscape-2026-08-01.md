# Agent 对话工作区设计参考

更新时间：2026-08-01

本次参考通过公开产品文档和当前页面结构完成，目标不是复制品牌视觉，而是提取适合 UAI Forge
控制面的交互模式。

## 参考来源

| 产品 | 公开来源 | 观察到的模式 |
|---|---|---|
| ChatGPT | [Projects in ChatGPT](https://help.openai.com/en/articles/10169521-projects-in-chatgpt) | 侧栏承载长期项目和多个聊天；文件、指令、聊天共同组成工作上下文；可从新项目开始并继续已有工作。 |
| Claude | [What are projects?](https://support.claude.com/en/articles/9517075-what-are-projects) | 每个项目拥有独立聊天历史和知识库；项目指令与知识在项目内生效；共享项目明确区分查看和编辑权限。 |
| Cursor | [Cursor 文档](https://cursor.com/cn/docs) | Agent、规划、评审、工具、技能、MCP 和子代理被组织在同一套工作区导航中；中文界面保留稳定的 Agent、MCP 等代码术语。 |
| Vercel AI SDK | [AI SDK UI Chatbot](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot) | 对话 UI 需要消息持久化、恢复流、工具使用和错误处理；工具过程应该可观察但不阻塞主对话阅读。 |
| Replit Agent | [Plan Mode](https://docs.replit.com/features/agent/plan-mode) | Plan 从输入框模式选择进入；复杂任务先生成结构化任务列表，用户可以继续对话修改，也可以批准后进入 Build。 |
| Claude Code | [Permission modes](https://code.claude.com/docs/en/permission-modes) | Plan 是只读研究与提案阶段；计划完成后明确提供批准、继续规划或编辑计划的分支，批准会退出 Plan。 |
| Cursor Agent | [Plan 模式](https://cursor.com/docs/agent/modes) | 复杂关键词可建议 Plan；先澄清、检索代码库、生成可编辑方案，准备好后再开始构建，简单任务直接 Agent。 |
| Kiro CLI | [Terminal UI](https://kiro.dev/docs/cli/terminal-ui/) | 思考块默认流式展示，长内容收成 tail view 可展开；工具有标题、spinner、完成状态、可折叠输出，另有独立 Activity tray。 |

## 设计结论

1. Agent 对话应该是控制面的一等工作区，而不是运行记录中的一个弹窗入口。
2. 左侧列表适合承载会话上下文和快速切换；中央区域保持单一阅读方向；运行事件放入右侧可收起面板，避免工程细节压过回答。
3. 发送消息后先显示用户消息和运行中状态；只有收到 Run 终态或持久事件，才渲染成功、失败或取消，不能由前端猜测结果。
4. 工具调用使用“中文展示名 + 英文稳定 ID”的双层信息：中文负责理解，ID 负责排障、复制和与 Agent 配置对应。
5. 0.1.x 不新增 Session 表。会话侧栏只聚合现有 Run 的 `session_id`，URL 保存当前运行上下文；这避免引入第二个事实源，同时为后续 Session 合同保留演进空间。
6. 回答表面不应把正文、思考摘要和 Trace 诊断都包进同一张高对比度卡片；主流 Agent 产品更倾向于无框助手正文、轻量用户气泡、可折叠活动状态，以及进入诊断详情的明确入口。

## UAI Forge 采用的工作区

```text
Agent 对话
├── 会话侧栏：新建对话、按 session_id 聚合、显示 Agent / 最近状态
├── 中央对话：用户输入、Agent 输出、运行中/失败/取消、换 Agent
└── 运行详情：事件数量、游标、模型/工具/委派事件，可折叠查看
```

回答表面采用“正文优先”的层级：常用 Markdown 在前端安全投影为段落、标题、列表、加粗和
行内代码；公开执行阶段保留在正文下方的低强调活动条，完整 Trace 继续放在运行详情。

本设计沿用 UAI Forge 当前的浅色控制台和低饱和蓝主操作色、绿色状态色，不引入品牌依赖、第三方 Agent SDK 或
独立聊天后端。

## 2026-08-01 新鲜公开检索结论

本轮通过 Google 以 `agent chat UI thinking collapse task monitor plan mode` 检索，并直接核对
Replit、Claude Code、Cursor 和 Kiro 的公开文档。可落地的共同模式不是“把所有内部思考铺开”，
而是把用户可介入的状态分成三层：

1. **主回答层**：回答持续流式出现；运行中的阶段用一行低强调活动摘要表达。
2. **协作层**：复杂度足够时自动生成 Todo/任务列表；Plan 由用户在输入框主动选择，生成后
   进入可编辑、可批准、可继续规划的审阅状态。
3. **诊断层**：工具输出、模型/Agent 事件和完整 Trace 放在可收起的侧栏或 Activity tray；终态
   默认折叠，用户需要时再展开。

这也解释了当前页面“看起来不是一个水平”的核心差距：不是缺少更多事件，而是默认信息层级反了。
