---
kind: adr
id: ADR-0001
status: accepted
date: 2026-07-30
---

# ADR-0001：采用协议优先的自有核心

## 背景

AgentScope、LangGraph、OpenAI Agents SDK、PydanticAI 等框架各有有价值的运行原语，但
其消息、工具、状态和部署 API 的稳定节奏不同。把任一框架类型写入持久数据或公共 API，
会让替换成本扩散到 Runtime、Web、插件和历史记录。

## 决定

- 核心领域、Pydantic 模型、HTTP/Event/Plugin 合同由 UAI Forge 自己定义。
- 第三方框架和供应商 SDK 仅出现在 adapter package。
- 端口使用 Python `Protocol`/ABC 和 JSON Schema/OpenAPI 合同。
- MCP、A2A、AG-UI、OTel 是边缘协议，不是核心领域对象。

## 结果

优点：

- 模型、存储、消息总线和编排实现可替换。
- 合同可单独版本化和做兼容测试。
- 可选择性吸收开源理念而不继承整个依赖图。

代价：

- 需要维护 adapter 和 TCK。
- 不能直接暴露第三方框架的全部高级功能。
- 必须显式定义语义，不能把第三方行为当作隐含规范。

## 拒绝方案

- 直接以 AgentScope Service 数据模型作为公共 API。
- 让 LangChain Message/Runnable 成为持久类型。
- 同时支持多套核心消息对象并在业务代码中分支。
