---
kind: change-proposal
id: CHG-0038-PROPOSAL
status: in_progress
target: 0.1
---

# 有界上下文与可复用研究证据

长时间自进化 Run 当前会反复携带完整的工具结果、会话记忆和委派输出。输入缓存虽然
可见，但不能替代上下文边界；过大的请求会增加延迟、失败率和实际令牌消耗。该 change
为 Runtime 增加工具结果和历史轮次的有界策略，并把研究问题、来源、结论和 UAI 转译
沉淀为可提交的 Markdown 证据。

该 change 不设置固定的研究次数或“小任务”上限，也不把缓存命中误认为无限预算；Agent
仍可在策略预算内进行系统性、多文件和跨阶段演进。
