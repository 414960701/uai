---
kind: change-proposal
id: CHG-0032
status: accepted
target: 0.1
date: 2026-08-02
implementation_status: implemented
requirements:
  - OBS-011
  - UI-011
---

# 模型 Token 缓存命中可观测性

模型调用目前只把输入、输出和总 token 用量写入 `model.completed`。OpenAI-compatible
接口和 Anthropic Messages 接口还会返回输入缓存读取/写入计数，但这些计数在适配器边界
被丢弃，用户无法判断一次调用是否命中缓存，也无法在多步 Run 中逐次核对缓存效果。

本变更为 UAI Forge 增加 provider-neutral 的缓存 token usage 字段，保留供应商字段只在
适配器内映射；运行时在流式 usage 分片之间合并计数；Trace 和对话公开摘要在每个模型
调用完成条目中显示缓存命中信息。未报告缓存计数的旧事件或 Provider 显示“未报告”，
不把未知值伪装成零，也不展示 prompt、凭证或 Provider 对象。
