---
kind: design-delta
id: CHG-0004-DESIGN
status: accepted
target: 0.1.x
---

# Design delta

`PluginRegistry` 在注册 manifest 时按声明 dialect 编译 Schema，并以 `(kind, plugin_id)` 缓存
validator。`validate_agent_spec` 是统一 gate；API create/PATCH 与
`ValidatedAgentRepository` 防止无效 revision 落盘，RunManager 防止无效 Run 记录落盘，
Runtime 对 root 和每个 bounded child frame 再校验，覆盖旧数据与替代 Repository。

错误只返回 code、plugin/tool ID、JSON Pointer path 和失败 keyword，不包含实例值或
jsonschema 原始 message。

Runtime 从实际 ToolPlugin 的 `parameters` 编译调用 validator。provider 输出先验证，
middleware 可进一步收紧或变换参数，但变换结果在 `invoke` 前再次验证。delegation 使用
同一路径和固定参数 Schema。

进程内 memory 拆为共享数据 backend 与每次 binding 创建的策略 view；`enabled=false`
时 Runtime 不调用 factory，从而避免“停用但仍保留会话”的隐式行为。
