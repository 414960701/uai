---
kind: requirements-delta
id: CHG-0038-REQUIREMENTS
status: in_progress
target: 0.1
---

## CTX-001 — 工具结果上下文上限

WHEN 普通工具或委派 Agent 返回结果给模型
THE SYSTEM SHALL 通过统一的 provider-neutral 序列化路径限制单个结果的上下文字符数；
被截断的结果 SHALL 给出可操作的提示，使 Agent 能通过更窄的读取请求取得缺失范围。

## CTX-002 — 历史轮次压缩

WHEN 一次 Run 的模型历史超过消息数或字符数防线
THE SYSTEM SHALL 保留系统合同、当前用户任务和最近的完整 assistant/tool 轮次，允许
丢弃旧会话记忆和旧工具轮次；不得只保留 assistant 工具调用而丢失对应的 tool result。

WHEN Runtime 压缩历史
THE SYSTEM SHALL 追加公开、有界的 `agent.progress` 度量事件，且不得把凭据、原始
授权头或隐藏推理写入事件、日志或持久化快照。

## CTX-003 — 缓存与预算语义

WHEN Provider 报告缓存命中或缓存创建令牌
THE SYSTEM SHALL 将其作为 `TokenUsage` 的输入令牌元数据展示；缓存字段 SHALL 不改变
UAI Forge 的总令牌、步骤、工具调用、超时或取消预算。

## RES-001 — 研究证据复用与沉淀

WHEN 自进化 Agent 开始公开资料调研
THE SYSTEM SHALL 先读取 `docs/research/README.md` 和相关已有笔记，识别已有结论与
未决问题；仅对新的问题、来源或版本变化进行增量研究。

WHEN 研究结论被用于规范、实现或测试
THE SYSTEM SHALL 在 `docs/research/` 记录可复核来源、事实/推断、UAI 转译、取舍、风险、
traceability 和下一步问题，并将文档与代码/测试一并提交；不得持久化任何秘密。

## RES-002 — 公开来源边界

研究 SHALL 只访问公开网页、官方文档、公开源码和标准资料；登录页、私有仓库、凭据、
cookie、授权头和私密网络地址不得作为研究输入或输出。
