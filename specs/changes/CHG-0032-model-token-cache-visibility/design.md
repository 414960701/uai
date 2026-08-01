---
kind: design-delta
id: CHG-0032-DESIGN
status: implemented
target: 0.1
---

# 设计决策

1. `ports.py::TokenUsage` 增加 `cached_input_tokens` 和
   `cache_creation_input_tokens` 两个可空、非负的 provider-neutral 字段。`None` 表示
   Provider 没有报告，`0` 表示 Provider 明确报告没有该类 token；两者都是输入 token 的
   细分，不改变现有 `total_tokens = input_tokens + output_tokens` 预算语义。
2. OpenAI-compatible 适配器读取 `prompt_tokens_details.cached_tokens`、兼容的
   `input_tokens_details.cached_tokens` 和常见的 `prompt_cache_hit_tokens`；Anthropic
   Messages 适配器读取 `cache_read_input_tokens` 与 `cache_creation_input_tokens`。
   供应商方言只存在于 `providers.py`。
3. Runtime 合并流式 usage 分片的非缺失维度，避免 Anthropic 的 `message_start` 输入/缓存
   信息被后续 `message_delta` 输出信息覆盖；fallback usage 保持现有行为。
4. 前端使用一个安全的 usage formatter，在 Trace 的模型完成事件、公开执行摘要和 Trace
   汇总中显示“缓存命中”；不依赖 raw payload，也不把未报告解释成零。
