---
kind: requirements-delta
id: CHG-0002-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### UI-001A — 可追踪的 Agent 修订编辑

WHEN 操作者创建或编辑 Agent
THE SYSTEM SHALL 可配置 provider/model 及非 Secret JSON 配置、工具别名/权限/配置、
memory、middleware、子 Agent mount 和执行策略；编辑 SHALL 携带期望 revision 并发布新
revision，不原地改写历史。

### UI-001B — 明确的 Mount 与 Instance 配置

WHEN 操作者挂载子 Agent 或创建运行实例
THE SYSTEM SHALL 显示并保存 mount alias、目标 revision、并发、输入模板和下游工具插件
范围，以及 Instance 的固定 Agent revision、environment、capacity 和 ready/stopped
状态。界面 SHALL 把 environment 标记为运行上下文标签，不得暗示自动创建云资源。

### RUN-002A — 真实 Run history

WHEN 操作者打开 Run 详情
THE SYSTEM SHALL 从 `/runs/{id}/events/history` 读取真实持久事件，按单调 sequence 展示
数量、类型、Agent、深度和脱敏摘要；接口失败 SHALL 明确显示错误而不是生成假事件。

### UI-002A — 能力状态不得伪装成设置

WHEN 一项策略没有可写的服务端配置 API
THE SYSTEM SHALL 以只读能力状态呈现。尚未实现的可恢复云集群 SHALL 标记为规划，不使用
会暗示立即切换的控件。
