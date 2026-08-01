---
kind: design-delta
id: CHG-0017-DESIGN
status: implemented
target: 0.1
---

# 快速澄清与 Trace 耗时设计

1. `routing.fast_path` 只作为 Agent 已有 `labels` 中的声明式值；运行时只接受白名单值
   `weather_missing_location`，未知值 fail closed。当前天气 Agent 通过标签启用，不改变
   核心 Agent/Provider 对象契约。
2. 快速路径在 root frame 的上下文准备之后执行。它发布 `agent.progress` 的
   `preflight`/`clarifying`/`completed` 阶段和 Agent/Run 终态事件，不发布模型、工具或委派
   事件，也不写入 Agent memory。
3. 模型、工具、委派和 Agent frame 在开始处记录单调时钟；完成/失败事件只携带四舍五入后的
   `duration_ms`。事件时间戳仍是跨进程/回放可用的事实，单调时钟只用于计算本次持续时间。
4. 前端以 `span_id`、事件类型和稳定调用标识配对 start/complete；运行中使用当前时间显示
   “进行中 · X.X 秒”，终态使用事件里的 `duration_ms`。运行记录增加小型耗时分解，不把
   `model.delta` 逐片段当作独立阶段。
5. 快路径和 Trace 展示继续遵守 CHG-0016：公开阶段是安全摘要，不展示原始 chain-of-thought、
   prompt、凭证或完整工具参数。
