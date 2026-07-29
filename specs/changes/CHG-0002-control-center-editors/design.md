---
kind: design-delta
id: CHG-0002-DESIGN
status: accepted
target: 0.1.x
---

# Design delta

Control Center 保留结构化常用字段，并为扩展的 `config` 使用 JSON 对象输入。前端先验证
JSON 语法和对象形状，后端 Pydantic、插件 Schema 与明文 credential 拒绝规则仍是权威。

Agent PATCH 总是携带 `expected_revision`。工具和 mount 编辑器保留未修改绑定的配置；
新增 mount 默认钉住当前 revision，并以 `allowed_tools = null` 继承上游范围；显式空列表
表示该子树拒绝全部插件工具。Instance 继续单独引用 Agent revision；environment 仅作为
上下文标签呈现，不触发本地、容器或云端调度。

Run 详情只消费真实 history；页面不建立第二套事件事实源。安全能力与部署能力使用状态行，
不维护脱离服务端的 React 假开关。

长表单采用固定头尾、内容滚动；桌面策略字段三列，窄屏单列。视觉使用白/浅灰、低饱和绿、
轻边框和弱阴影。
