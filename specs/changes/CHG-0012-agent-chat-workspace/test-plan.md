---
kind: test-plan
id: CHG-0012-TEST-PLAN
status: implemented
---

# Test plan

## 前端源与渲染

- 导航包含“Agent 对话”，工作区包含会话侧栏、消息输入和运行详情。
- 对话发送使用 `agent_id`、输入和 `session_id` 调用现有 Run API。
- 事件历史、SSE、sequence 去重、重连和有界降级路径仍然使用共享 API/reducer。
- 失败/取消不被渲染为成功；重试创建新 Run。
- 中文映射覆盖内置工具、记忆、中间件、存储、事件总线和 UI 扩展；稳定 ID 仍在源码或详情中可见。
- 不出现 API Key/Secret 持久化到 localStorage、URL 或消息数据的实现。

## 浏览器 smoke

1. 从导航打开 Agent 对话，创建新会话并选择 Agent。
2. 发送一条消息，观察用户消息、运行中状态、助手终态和 Run ID。
3. 展开工具/模型事件，验证中文名 + 英文 ID；刷新后从 URL 恢复当前 Run。
4. 取消运行或制造失败，验证终态文案与重试路径。
5. 在 390px 宽度下完成选择、发送、展开详情和 Escape 收起。

## 必跑命令

```bash
npm run lint
npm run typecheck
npm test
python -m pytest backend/tests -q
```

本变更继续使用 0.1.x 单进程 Run/SSE 边界，不将浏览器 smoke 结果写成分布式恢复或持久 Session 证据。
