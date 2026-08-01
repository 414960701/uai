---
kind: change-proposal
id: CHG-0014
status: implemented
target: 0.1
date: 2026-08-01
implementation_status: implemented
requirements:
  - THINK-001
  - THINK-002
  - THINK-003
---

# Agent 思考模式选择

Agent 对话目前只能发送普通 Run；用户无法明确选择让当前模型关闭思考、自动跟随模型，
或请求开启受支持的推理参数。本变更为 Run 和 UAI Forge Provider 契约增加受治理的
`thinking_mode`，并在 Agent 对话与“发起运行”入口提供中文选择器。

思考模式是请求偏好，不是原始 chain-of-thought 展示开关。Provider 只在自身协议或模型
配置声明可识别的参数时映射 `on/off`；未知 OpenAI-compatible 方言保持兼容并在公开阶段
显示降级提示。任何 reasoning/thinking block 仍不得进入事件、Trace 或前端。
