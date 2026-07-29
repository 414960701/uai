---
kind: requirements-delta
id: CHG-0001-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### CORE-003A — Instance override 白名单

WHEN 客户端创建、更新或读取 Agent Instance
THE SYSTEM SHALL 用 `extra=forbid` 的显式合同限制 `config_overrides`，在 `0.1.x` 只接受
可选的 `policy` 及其已声明字段，并拒绝身份、prompt、provider/model、工具、子 Agent、
权限、memory、middleware、明文凭据和所有未知字段。

### CORE-003B — 有效策略只可收紧

WHEN Run 通过 Instance 引用不可变 Agent revision
THE SYSTEM SHALL 对每个数值策略字段取 definition 与 Instance override 的较小值，对
`fail_fast` 取更严格的布尔值，并用完整 `AgentSpec` Pydantic 合同重新校验临时 effective
spec；不得写回或改变任何 revision。

### CORE-003C — Instance 运行上下文

WHEN Run 通过 Instance 启动
THE SYSTEM SHALL 把 `instance_id` 与非敏感 `environment` 标识写入初始/终态 Run metrics、
`run.started` payload、模型 metadata 以及 middleware/tool context。

直接通过 Agent Definition 启动的 Run SHALL 保持兼容，并在统一上下文中使用空的
Instance 标识。

### SEC-001A — Override 不承载 Secret

WHEN override 输入任意层级出现常见明文 credential key
THE SYSTEM SHALL 在持久化 Instance 或创建 Run 之前拒绝；本 delta 不新增 Secret 解析。
