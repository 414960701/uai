---
kind: change-proposal
id: CHG-0003
status: implemented
target: 0.1.x
requirements:
  - MAG-003
  - MAG-006
  - SEC-004
---

# Bounded child 本地策略与 Mount 工具范围

## 问题

当前 bounded child 会消耗根 step/tool/token 账本，但只有 `max_steps` 通过本地循环间接
生效。Child 的 `max_tool_calls`、`token_budget`、`timeout_seconds` 和
`max_parallel_children` 没有独立约束；`ChildMount` 也没有工具权限范围。一个根预算较宽
或下游 mount 更宽的调用链可能绕过子 Agent 或上游 mount 的本地限制。

## 目标

- 每次 bounded Agent invocation 同时遵守根共享预算与该 Agent 的本地预算/深度。
- Child timeout 覆盖排队、取得并发许可和实际执行，且不能越过根 Run timeout。
- 并发同时受根调用树、当前父 Agent 和具体 mount 三个许可门约束。
- `ChildMount.allowed_tools` 使用插件 ID 白名单，沿调用树只可保持或收紧。
- 模型不可见被范围拒绝的工具；恶意 provider 即使伪造 tool call 也在执行前被拒绝。
- 保持旧 mount JSON 与既有行为兼容。

## 非目标

- 不实现 tenant PolicyEngine、RBAC、服务端 Approval 完整资源或 Secret/workspace scope。
- 不给 mount 增加 provider/model/prompt 覆盖。
- 不实现 durable peer 权限继承。
- 不改变 `ToolBinding.permission=confirm` 当前 fail-closed 行为。

## 风险与回滚

显式配置 `allowed_tools` 后，历史上可调用但未列出的工具将被拒绝；这是预期收紧。
未配置或为 `null` 的旧 mount 保持原行为。回滚可删除新字段并回退 Runtime 的本地账本，
数据库 schema 无变化，但已保存 revision 的 JSON 仍可由默认字段兼容读取。

## 实现证据

2026-07-30：Python 3.9.6 执行
`.venv/bin/python -m pytest backend/tests -q`，`42 passed`；专项 child policy/scope
测试 11 项全部通过。
