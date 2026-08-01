---
kind: test-plan
id: CHG-0032-TEST-PLAN
status: executed
---

- Provider：OpenAI-compatible 完成/流式响应映射 `cached_tokens` 和 DeepSeek 风格命中字段。
- Provider：Anthropic 完成/流式响应映射 cache read/create 字段，并保留跨事件的完整 usage。
- Runtime：多 usage chunk 不覆盖已获得的输入、输出或缓存维度，`model.completed` 带完整计数。
- UI：模型完成事件逐调用显示输入、输出、缓存命中/写入；旧事件和未报告字段显示“未报告”。
- 回归：运行时预算、Provider 协议、SSE/Trace 和前端 lint/typecheck/build/test 保持通过。

必跑命令：

```bash
python -m pytest backend/tests -q
npm run lint
npm run typecheck
npm test
```
