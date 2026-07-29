---
kind: change-proposal
id: CHG-0001
status: implemented
target: 0.1.x
requirements:
  - CORE-003
  - SEC-001
  - OBS-001
---

# Instance 运行时安全覆盖

## 问题

`AgentInstance.config_overrides` 当前接受任意字典，但 Run 解析目标后直接执行原始
`AgentSpec`。这既让控制面展示的配置与实际执行不一致，也给未来把任意字段合入不可变
revision 留下了安全风险。`environment` 和 Instance 身份也没有进入插件可见的运行上下文。

## 目标

- 为 `config_overrides` 提供显式、默认拒绝的 Pydantic 合同。
- `0.1.x` 只允许收紧根 Agent 的执行策略，不允许替换身份、prompt、插件、工具或子 Agent。
- 每次 Instance Run 构造并完整校验临时 effective `AgentSpec`，不修改 revision 历史。
- 将非敏感的 `instance_id`、`environment` 写入 Run metrics、`run.started` 和插件运行上下文。

## 非目标

- 不实现 deployment profile、云调度、desired/observed state 或多 worker。
- 不覆盖 provider/model/tool/memory/middleware/children 配置。
- 不解析、保存或传播 Secret 值。
- 不修复 Instance capacity 热更新；该问题保留为 `CORE-003` 的独立缺口。

## 风险与回滚

此前未受约束的 override 会被拒绝；这是安全边界的有意 fail-closed 收紧。回滚只需停止
写入带 override 的 Instance，并回退本变更；不可变 Agent revision 和数据库 schema 不变。

## 实现证据

2026-07-30：`source .venv/bin/activate && python -m pytest backend/tests -q`，
`30 passed`。
