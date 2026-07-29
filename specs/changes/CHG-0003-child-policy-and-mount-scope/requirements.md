---
kind: requirements-delta
id: CHG-0003-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### MAG-003A — 根预算与 invocation 本地预算

WHEN root 或 bounded child 消耗 model step、tool call 或 token
THE SYSTEM SHALL 对根共享账本和当前 Agent invocation 本地账本各扣减一次；任一上限先到
即 fail closed。根 Agent 的本地账本与根账本是同一对象，不得重复扣减。

### MAG-003B — Child 本地 timeout

WHEN Parent 调用 mounted child
THE SYSTEM SHALL 以 child `timeout_seconds` 限制从等待本地/mount/根并发许可到 child 返回
的整个 bounded invocation；根 Run timeout 仍是调用树外层上限。

### MAG-003C — 分层并发交集

WHEN Agent 同一步并行发起多个 bounded child
THE SYSTEM SHALL 同时取得根 `max_parallel_children`、当前父 Agent
`max_parallel_children` 和 mount `max_concurrency` 的许可。等待下一层调用时仍须转让
已持有的根 lease，且取消/异常不得泄漏许可。

### MAG-003D — Mount 工具权限交集

WHEN child 或其后代准备暴露或执行 ToolBinding
THE SYSTEM SHALL 令有效工具插件范围等于上游有效范围与当前 mount `allowed_tools` 的交集，
再与 child 已启用的 ToolBinding 和其 `permission` 相交。任何下游 mount 不得重新扩大
上游范围。

`allowed_tools` 的值是 `ToolBinding.plugin_id`：

- 字段缺失或 `null`：不新增限制，继承上游范围；root 的初始范围为全集。
- `[]`：本 mount 下整个 bounded subtree 不允许插件工具。
- 非空列表：只允许交集中的插件 ID；重复项或非法 ID 在配置边界拒绝。

被范围拒绝的工具 SHALL 不出现在模型 tool definitions 中；provider 伪造同名 tool call
仍 SHALL 在 tool/middleware 执行前被拒绝。

### MAG-003E — Ancestor 与 child 本地深度

WHEN bounded child 继续委派
THE SYSTEM SHALL 同时遵守 root/ancestor 的剩余深度与当前 child 的本地 `max_depth`。
`max_depth=0` 的 Agent 可作为 child 执行自身模型，但不得再启动下一层 delegation。
