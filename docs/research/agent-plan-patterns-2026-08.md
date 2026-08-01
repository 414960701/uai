# Agent 计划模式研究记录

日期：2026-08-01

这次研究关注的是“计划模式如何形成可审阅的协作闭环”，而不是如何把模型隐藏思考过程
展示出来。以下资料均为公开页面，结论只用于 UAI Forge 的产品设计，不把第三方对象带入
核心合同。

## 公开资料

- Claude Code 权限模式：<https://code.claude.com/docs/en/permission-modes>
  将 plan 定义为只读探索和提案阶段；计划完成后由用户选择继续规划、编辑计划或批准并
  切换到执行权限。核心是权限边界和人工批准，不是一个 prompt 开关。
- Cursor Plan Mode 文档：<https://cursor.com/docs/agent/modes>
  先追问澄清、检索代码库、生成可审阅计划；计划可以继续对话修改，准备好后再开始构建。
- Cursor Plan Mode 产品说明：<https://cursor.com/blog/plan-mode>
  计划会生成带文件路径和代码引用的 Markdown，可内联编辑，也可以保存到工作区供团队
  复查。
- OpenAI ExecPlan 实践：<https://developers.openai.com/cookbook/articles/codex_exec_plans>
  把计划当作自包含、可持续更新的设计文档，要求记录进度、发现、决策和验收，保证中断后
  可以从计划恢复工作。
- LangChain Plan-and-Execute：<https://www.langchain.com/blog/planning-agents>
  把规划器、执行器和重新规划分开；复杂任务先形成多步计划，执行结果再决定完成还是
  重新规划。更高阶的实现会把步骤和依赖组织成 DAG，但那属于后续执行优化。
- Claude Code Agent View：<https://code.claude.com/docs/en/agent-view>
  把多个会话按 Needs input、Working、Completed 等状态分组；用户先用 peek 看摘要，
  需要时再 attach 进入完整会话。可见状态优先于完整事件流。
- OpenAI Deep Research FAQ：<https://help.openai.com/en/articles/10500283-deep-research-faq>
  复杂任务先生成可修改的 research plan，用户可在开始前审阅、运行中跟随进度并中断
  调整来源，完成后得到带引用的结构化报告和 activity history；快速问题则回到普通聊天。
- OpenAI Codex CLI features：<https://developers.openai.com/codex/cli/features/>
  把搜索、子 Agent、审查和当前活动作为同一条可跟随工作流，强调“看见活动、需要时介入”，
  而不是把所有内部事件默认铺在对话里。

## 对 UAI Forge 的落地结论

当前单进程基线先实现最小、可回放的闭环：计划 Run 只产生公开文本和结构化计划；计划有
独立 ID、版本、步骤、假设、风险和状态；用户可以修改、拒绝或批准；批准创建引用计划
版本且固定根 Agent 修订的执行 Run；计划动作和执行结果都写入同一事件历史可观察。

0.1 不把计划误称为完整的分布式 Approval 资源，也不允许计划模式执行工具、委派或外部
 副作用。工具只读探索、持久化计划文件、并行 DAG 调度、服务端身份审批和崩溃恢复继续
 按 foundation 规范列为后续能力。

## 对话层落地结论

- 主线优先：普通回答保持平面消息流，运行详情不在进入聊天时自动打开。
- 状态分层：运行中的阶段显示一行活动摘要；完成后只留可展开的公开摘要；详细事件统一
  进入 Trace。
- 任务按需出现：复杂 execute Run 显示 Todos / Artifacts / Skills & MCP 监视器，简单
  问答不强制出现任务面板。
- 选择必须是动作：选择卡要明确单选/多选、必选/可跳过、推荐项，以及 Continue/Skip；
  选择结果进入 Run 事件而不是混在普通文本里。
