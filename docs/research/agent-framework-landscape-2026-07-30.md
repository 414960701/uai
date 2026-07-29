---
kind: informative
id: RESEARCH-AGENT-LANDSCAPE-2026-07-30
status: complete
last_reviewed: 2026-07-30
---

# 开源 Agent 框架调研

调研日期：2026-07-30。版本和项目状态只代表该日期可从官方仓库、文档或包索引
核验的情况。本项目不复制任一框架的内部 API；调研用于选择领域边界和质量属性。

## 调研方法与证据等级

- 版本以 PyPI package JSON 或官方 release 为准，不从博客、搜索摘要或模型记忆推断。
- 能力以官方文档、仓库 README、公开合同和源码为主证据；路线图能力不能写成已交付。
- 维护状态以项目所有者的 README/公告为准；Star、下载量只代表关注度，不代表生产质量。
- 对认证、分布式、恢复、隔离和 exactly-once 等高风险声明采用否定式核验：官方若标注
  WIP、experimental 或要求部署者自行实现，比较表必须保留该限制。
- 研究结论通过自有领域合同落地；若只能依赖第三方内部类型才能实现，则不进入内核。

## 结论

不存在一个应被整体照搬的项目。UAI Forge 的基线组合是：

- 从 AgentScope 2.0 借统一事件、权限、中间件、Workspace 与 Agent Service 边界。
- 从 LangGraph 和 Microsoft Agent Framework 借持久状态机、checkpoint、恢复与 HITL
  的完整版本方向。
- 从 PydanticAI 借强类型请求、依赖注入、Toolset 和 Provider 能力协商。
- 从 Agno 借 Agent / Team / Workflow / AgentOS 与后台控制面的产品分层。
- 从 OpenAI Agents SDK 借 handoff、guardrail、session 和 trace 的简洁开发体验。
- 从 Google ADK 借 Runner / Event / SessionService 和本地/远程子 Agent 统一入口。
- 从 LlamaIndex Workflows 借 typed event → step 的低耦合事件工作流。
- MCP、A2A、AG-UI 和 OpenTelemetry 只作为边缘标准，不成为内部领域模型。

内核应保持自有、最小、版本化；第三方变化只影响适配器。

## AgentScope 2.0 深入分析

截至调研日，官方仓库将 2.0 描述为 production-ready；PyPI/仓库可核验版本为
2.0.5（2026-07-23），latest 文档已指向 2.0.6dev。仓库为 Apache-2.0，
Python 包分类仍包含 Beta。正式文档和 README 展示的核心是：

1. 无状态 Agent 推理/行动循环与显式 `AgentState` 持久化。
2. `Msg` 与细粒度 `AgentEvent` 双模型；事件可直接驱动前端和 HITL。
3. Toolkit、工具权限、Middleware、Context、长期记忆、RAG。
4. Local、Docker、E2B、OpenSandbox、Daytona 等 Workspace/Sandbox 后端。
5. FastAPI Agent Service：多租户/多会话资源生命周期、SSE 重放、计划任务、
   后台工具、Workspace、Storage 和 MessageBus。
6. Agent Team：成员拥有独立 session，通过 Redis inbox/wakeup/message bus 协作，
   不只是同一 Python 调用栈中的对象嵌套。

### 值得采用

- 事件是一等公民。模型、文本块、工具、权限、状态变化都通过统一流呈现。
- Middleware 覆盖 reply、reasoning、acting、model call、context compression 和
  system prompt 等生命周期位置，追踪、预算、RAG、长期记忆可以组合接入。
- Agent Service 把存储、消息总线、Workspace、后台任务和调度作为构造参数，
  而不是藏在 Agent 类里。
- Schema-driven UI：凭据和模型公开 JSON Schema/能力卡片，避免前端写死提供商。
- 资源隔离粒度明确为 per-agent、per-session 或 per-user。

### 不直接照搬

- 官方文档仍把 distributed deployment 标为 WIP，不能把单机能力表述成已完成分布式。
- 服务不内建用户认证，示例 `X-User-ID` 必须替换，不能当作租户安全。
- 仓库有丰富基类，但没有成熟的 PyPA entry-point 插件发现、插件协议独立版本和
  兼容矩阵；UAI Forge 将这些作为核心质量属性。
- Agent Team 偏 durable peer session；本项目同时需要低开销的 bounded nested call。
- 内部 API 随 2.0.x 快速演进，直接耦合会把升级成本带入内核。

### 理念到 UAI Forge 的转化

| AgentScope 2.0 观察 | UAI Forge 的转化 | 当前证据 |
|---|---|---|
| 统一 AgentEvent 驱动 UI/HITL | Run 内事件信封、单调 sequence、持久化后再 SSE 扇出 | `RunEvent`、`EventBroker`、SSE 回放测试 |
| Agent Service 管理 Agent 之外的生命周期 | FastAPI 控制面、Repository、Runtime、EventBroker 分离组装 | `container.py`、`api.py`、`runtime.py` |
| Agent/Session/Workspace 有独立资源边界 | Definition revision、Instance、Session key、Run 分开；Workspace 留作正式端口 | `models.py`、`storage.py`、ADR-0002 |
| 子 Agent 由 Team 工具创建和协调 | 先实现受限、可审计的 Agent-as-tool 挂载；durable peer session 明确后置 | `ChildMount`、`AgentGraphValidator`、`AgentRuntime._delegate` |
| 权限规则和工具级检查共同决策 | 当前基线使用 `auto/confirm/deny` fail-closed 策略；完整 Policy Engine 纳入路线图 | `ToolBinding.permission`、权限欺骗回归测试 |
| Workspace 支持本地/容器/远程后端 | 借鉴“执行环境是端口”的理念，不依赖 AgentScope Workspace 类型 | `WorkspaceProvider` 目标端口与部署 ADR |
| Schema-driven frontend | 插件 manifest 暴露 `config_schema` 与 capabilities，后台按合同展示目录 | `PluginManifest`、`PluginRegistry`、插件 API/UI |

转化不是兼容层：UAI Forge 运行时不导入 AgentScope。AgentScope 2.0 当前要求
Python 3.11+，而本项目公共运行基线为 Python 3.9+；自有合同也避免把第三方的快速
minor 版本变化传播到 Agent 配置、事件和插件 API。

## 横向比较

| 项目 | 调研日状态 | 最值得参考 | 对 UAI Forge 的限制 |
|---|---|---|---|
| AgentScope 2.0.5 | Apache-2.0；latest 为 2.0.6dev | Event、Permission、Middleware、Workspace、Service、Team | 分布式 WIP；无内建认证；插件版本协商不足 |
| LangGraph 1.2.10 | 1.x 稳定/LTS 语义 | durable graph、checkpoint、interrupt/resume、长期执行 | 图模型不应成为所有 Agent 的强制编程范式 |
| Microsoft Agent Framework 1.12.1 | MIT；AutoGen/Semantic Kernel 新项目的官方汇合方向 | Agent + Workflow、checkpoint、HITL、time travel、OTel、DevUI | 部分 Python 子包仍 alpha/beta；不能绑定其类型 |
| PydanticAI 2.20.0 | MIT；2.x | 类型化依赖/输出、Toolset、Provider、Agent spec、Temporal 适配 | 事件与 OTel 的 minor API 仍可能变化 |
| Agno 2.8.5 | Apache-2.0 | Agent/Team/Workflow/AgentOS、RBAC、多租户、SSE/WS、配置版本 | UI/托管能力需单独核验；默认遥测需注意 |
| Google ADK 2.5.0 | Apache-2.0；快速迭代 | Runner、Event、SessionService、Task、subagent、A2A | 双周更新、2.0 破坏变更、部分协议仍实验 |
| OpenAI Agents SDK | MIT | handoff、guardrail、session、trace，概念少且开发体验好 | 提供商与运行模型偏特定，不作为通用内核 |
| LlamaIndex Workflows 2.22.2 | MIT | typed event → step、at-least-once 执行 | 默认无持久 checkpointer；step 重试要求业务幂等 |
| AutoGen | 官方 README 为 Maintenance Mode | actor/message/team 的历史设计经验 | 新项目官方已导向 Microsoft Agent Framework |
| Semantic Kernel | 新 Agent 工作导向 Microsoft Agent Framework | 插件/Planner/Process 分层经验 | Agent Orchestration/Process 仍有 experimental 面 |
| CrewAI | 活跃开源项目 | 声明式 Agent、Crew、Flow 的易用配置 | 高层抽象不应侵入执行内核 |
| CAMEL / MetaGPT | 研究与角色化协作代表 | role-playing、software-company workflow、评测案例 | 偏研究/固定协作模式，非通用生产控制面 |
| smolagents | Hugging Face 轻量框架 | 小内核、CodeAgent、工具与模型适配简洁 | 治理、持久化和后台不是主要目标 |

## 两种多 Agent 语义

框架必须同时支持，不能用一个模糊的“subagent”覆盖：

### Bounded nested call

父 Agent 把已挂载子 Agent 当作结构化工具调用。子调用继承 correlation、deadline、
取消、预算和权限交集；返回结构化结果。适合本次 `0.1.0` 的低延迟本地协作。

### Durable peer session

每个成员拥有独立 session/inbox/checkpoint，通过持久 MessageBus 交换有
correlation/causation 的消息；worker 释放后仍可恢复。适合长期任务、计划任务、
后台工具和跨进程云部署，列入 V1。

## 扩展性比较与设计结论

开源框架常把“可继承一个 Base 类”称为扩展性，但生产框架还需要：

1. **发现与契约分离**：entry point 只定位插件；manifest、协议版本和能力才决定能否加载。
2. **能力协商**：需要 structured output、parallel tool calls 等能力时 fail closed，
   不能根据版本名猜测或静默降级。
3. **独立版本轴**：Core、Plugin API、HTTP API、Event、Config、State Schema、UI SDK
   分别版本化。
4. **TCK**：Provider、Tool、Memory、Storage、Bus、Scheduler、Middleware、UI
   都需要 conformance tests。
5. **隔离**：内置可信插件可进程内；未知代码应在子进程/容器 plugin host 中运行。
6. **状态命名空间**：插件持久状态使用 plugin id + version + schema version，支持迁移和回滚。

当前实现完成 entry-point、manifest、协议主版本与能力目录；沙箱、签名、SBOM 和
完整 TCK 是后续发布门。

## 采用与规避清单

| 决策 | 采用 | 规避 |
|---|---|---|
| 核心模型 | 自有 Pydantic 合同 | 第三方 Agent/Message 类型泄漏 |
| 事件 | Run 内单调 sequence、持久重放、SSE | 宣称全局顺序或 exactly-once |
| 子 Agent | 挂载为受治理工具 + 未来 peer session | 直接把子对象/数据库交给父 Agent |
| 预算 | 根账本覆盖模型、工具、子 Agent | 只在调用结束后记账 |
| 插件 | manifest + protocol + capabilities + TCK | 任意 pip 包在线热加载 |
| 存储 | Repository adapter | 业务逻辑直接调用 SQLite/Redis |
| 标准 | MCP/A2A/AG-UI/OTel 适配器 | 外部协议成为内核真相 |
| 可观测性 | trace、审核摘要、usage、调用树 | 保存/展示原始 chain-of-thought |

## 官方来源

均访问于 2026-07-30：

- AgentScope repository: https://github.com/agentscope-ai/agentscope
- AgentScope PyPI metadata: https://pypi.org/pypi/agentscope/json
- AgentScope 2.0 documentation: https://docs.agentscope.io/
- AgentScope message and event: https://docs.agentscope.io/latest/en/building-blocks/message-and-event
- AgentScope permission system: https://docs.agentscope.io/latest/en/building-blocks/permission-system
- AgentScope middleware: https://docs.agentscope.io/latest/en/building-blocks/middleware
- AgentScope workspace: https://docs.agentscope.io/latest/en/building-blocks/workspace
- AgentScope Agent Service: https://docs.agentscope.io/latest/en/deploy/agent-service
- AgentScope Agent Team: https://docs.agentscope.io/latest/en/deploy/agent-team
- AgentScope paper: https://arxiv.org/abs/2402.14034
- LangGraph: https://github.com/langchain-ai/langgraph
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- AutoGen: https://github.com/microsoft/autogen
- Semantic Kernel: https://github.com/microsoft/semantic-kernel
- PydanticAI: https://github.com/pydantic/pydantic-ai
- Agno: https://github.com/agno-agi/agno
- Google ADK Python: https://github.com/google/adk-python
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- LlamaIndex Workflows: https://github.com/run-llama/workflows-py
- CrewAI: https://github.com/crewAIInc/crewAI
- CAMEL: https://github.com/camel-ai/camel
- MetaGPT: https://github.com/FoundationAgents/MetaGPT
- smolagents: https://github.com/huggingface/smolagents
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- A2A specification: https://github.com/a2aproject/A2A
- AG-UI: https://github.com/ag-ui-protocol/ag-ui
- OpenTelemetry GenAI conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
