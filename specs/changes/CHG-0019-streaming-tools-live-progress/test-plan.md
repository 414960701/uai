---
kind: test-plan
id: CHG-0019-TEST-PLAN
status: executed
---

- Provider：OpenAI-compatible 和 Anthropic 工具 SSE 片段聚合、tools payload、usage 与安全
  参数边界测试。
- Runtime：带工具的 streaming Provider 执行工具后继续发布多个 `model.delta`；工具 JSON
  不作为正文，非 streaming Provider 和 stream 失败回退保持兼容。
- Frontend：compact 只显示单行当前活动，展开后显示公开阶段轨迹；完整面板继续显示
  Trace/阶段；源断言确认隐藏 reasoning 边界。
- Regression：普通流式、工具、计划模式、思考模式、取消和 Trace 测试保持通过。
- Browser smoke：真实 Agent 发送带工具和普通消息，确认正文增量先于 `run.completed`，
  且聊天活动条随事件更新。

必跑命令：

```bash
python -m pytest backend/tests -q
npm run lint
npm run typecheck
npm test
```
