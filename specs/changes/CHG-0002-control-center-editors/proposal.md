---
kind: change-proposal
id: CHG-0002
status: implemented
target: 0.1.x
requirements:
  - UI-001
  - UI-002
  - RUN-002
---

# Control Center 高级配置与真实事件视图

## 问题

首个后台只能创建基础 Agent；修订编辑没有 mount、插件配置和完整执行策略，安全设置中的
本地开关也会让人误以为已经改变服务端策略。Run 详情曾使用演示时间线，无法作为运行证据。

## 目标

- 创建或修订 Agent 时配置模型、工具、记忆、中间件、mount 与执行策略。
- mount 可配置别名、固定修订、并发和输入模板；工具可配置别名、权限和 JSON 配置。
- 修订更新携带 `expected_revision`，并由后端发布不可变的新 revision。
- 管理多个固定 revision 的 Instance，并启用或停止它们。
- Run 详情读取持久化 history，按 sequence 展示真实委派、模型、工具、预算和终态事件。
- 未接通的安全与云能力只显示只读状态或规划，不伪装为浏览器本地开关。

## 非目标

- 不实现任意 JSON Schema 自动生成控件；第三方扩展配置暂用 JSON 对象输入并由后端校验。
- 不提供 Instance policy override 编辑、desired/observed controller、peer session 或 RBAC。
- 不让浏览器保存 API key；它只存在于当前页面内存。

## 兼容性

HTTP API 无破坏性变化。旧 Agent/Instance 继续可读；新字段本来已存在于 Pydantic 合同中。
前端演示模式仍可交互，但始终明确标记为演示数据。
