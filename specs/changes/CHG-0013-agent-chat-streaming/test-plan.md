---
kind: test-plan
id: CHG-0013-TEST-PLAN
status: executed
---

# Test plan

- Provider 流式解析：OpenAI-compatible / Anthropic SSE 文本块、usage、取消和缺少凭证。
- 运行时：无工具请求发布有序 `model.delta` 并聚合最终正文；有工具请求仍使用完整响应。
- 运行时：公开阶段和 trace/span/parent span 关联在根 Agent、子 Agent、模型、工具、预算和终态事件间保持一致。
- 前端：增量事件按 sequence 去重，刷新历史可重建正文，运行中显示正在输出，事件详情不被 token 洪泛。
- 拓扑：React Flow 节点/边来自当前 Agent 图，交互控件和窄屏状态可用。
- 运行记录：Trace 统计、筛选、展开详情、错误定位、耗时派生和安全字段断言。
- 回归：既有 Run/SSE、工具调用、失败、取消和重试测试保持通过。
- 真实浏览器：使用已配置模型发送普通消息，确认首个正文块先于 `run.completed` 出现。

必跑命令：

```bash
npm run lint
npm run typecheck
npm test
python -m pytest backend/tests -q
```
