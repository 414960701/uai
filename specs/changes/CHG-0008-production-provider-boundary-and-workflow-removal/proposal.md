---
kind: change-proposal
id: CHG-0008
status: implemented
target: 0.1.x
superseded_by: CHG-0009
requirements:
  - EXT-007
  - DEP-004
---

# 移除产品 Mock 与仓库 Workflow

> 历史说明：本变更的 provider catalog 断言在 CHG-0008 验收时成立；CHG-0009 后续以
> additive 的 Anthropic Messages 生产适配器和统一 `ModelConfig` 合同更新了当前 catalog。
> 本文保留当时移除 Mock/seed/workflow 的事实，不作为当前 provider 数量说明。

## 问题

产品运行时曾把离线演示 provider、启动 seed 和前端演示状态混在可运行路径中，
导致空数据库看起来像有业务数据，也让容器门禁依赖伪造模型。公开仓库还保留了
托管平台 workflow；本项目改为由维护者显式运行版本化门禁脚本。

## 范围

- 从产品 registry 和 provider 模块移除演示/测试 provider。
- 删除启动 seed、前端本地业务数据 fallback 和默认委派示例。
- 将 test-only provider 与拓扑夹具隔离到 `backend/tests`。
- 删除 `.github/workflows`，保留 Makefile、前后端测试和容器 smoke 作为显式门禁。
- 让容器 smoke 验证新数据库为空、provider 注册表正确且不写入业务数据。

## 非目标

- 不删除 Agent-as-tool、多 Agent 挂载或真实 OpenAI-compatible provider。
- 不把测试 provider 当作产品插件或公开控制 API 能力。
- 不改变已配置数据库中的用户 Agent；用户已选择不兼容旧 seed/mock 数据。
