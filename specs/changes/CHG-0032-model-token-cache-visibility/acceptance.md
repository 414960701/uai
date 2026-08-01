---
kind: acceptance
id: CHG-0032-ACCEPTANCE
status: complete
---

- [x] OpenAI-compatible 的 `prompt_tokens_details.cached_tokens` 被映射并逐调用显示。
- [x] Anthropic 的 cache read/create token 被映射并逐调用显示。
- [x] 流式 usage 分片合并后，模型完成事件保留输入、输出和缓存维度。
- [x] 未报告缓存字段的历史事件显示“未报告”，不伪造零值。
- [x] `python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck` 和 `npm test` 通过。
