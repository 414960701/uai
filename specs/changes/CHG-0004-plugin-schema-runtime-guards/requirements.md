---
kind: requirements-delta
id: CHG-0004-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### EXT-006A — Binding config fail closed

WHEN runtime-capable plugin 注册或 Agent revision 创建、更新、提交 Run、进入任一执行 frame
THE SYSTEM SHALL 校验 manifest Schema 自身、插件存在性/kind/可用性/factory 和完整 binding
config；失败 SHALL 使用稳定错误码且不得回显配置值。

### EXT-006B — Tool 与 delegation 参数二次验证

WHEN provider 返回 ToolCall 或 middleware 改写 arguments
THE SYSTEM SHALL 在 middleware 前和实际 invoke 前按 ToolPlugin 参数 Schema 验证；delegation
SHALL 使用 required/type/additionalProperties/maxLength 合同，失败时不得启动工具或子 Agent。

### EXT-006C — Memory binding 语义

WHEN MemoryBinding 被停用
THE SYSTEM SHALL 不创建、不读取、不追加 adapter。

WHEN 两个 MemoryBinding 使用不同 retention 配置
THE SYSTEM SHALL 分别应用各自策略，即使底层进程内 session 数据由同一 backend 保存。
