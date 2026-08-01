---
kind: design-delta
id: CHG-0014-DESIGN
status: proposed
target: 0.1
---

# 思考模式设计

1. `ThinkingMode` 是 UAI Forge 自有核心枚举，挂在 `RunRequest` 和 `ModelRequest`，不泄漏
   第三方 SDK 类型。
2. `RunManager` 将模式写入 `RunRecord.metrics.thinking_mode`；Runtime 复制到每次模型请求，
   `model.started` 只记录稳定的模式值。
3. Provider 适配器根据显式 `config.thinking_protocol` 或安全的模型目录推断映射方言；未识别
   时不向兼容接口追加未知字段。Anthropic extended thinking 的预算受 `max_tokens` 约束。
4. Provider 对返回中的 reasoning/thinking block 继续丢弃，只投影文本 delta；公开阶段在
   前端显示兼容提示，不展示原始思考内容。
5. 选择器默认 `auto`，切换只影响下一次 Run，不修改 Agent revision 或共享 ModelConfig。
