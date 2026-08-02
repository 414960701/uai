---
kind: change-proposal
id: CHG-0035-PROPOSAL
status: in_progress
target: 0.1
---

# 常规 Git 工作流工具

CHG-0034 已提供 tenant-scoped 加密工具凭证，但没有让工具消费 `credential_ref`。本 change
增加 UAI Forge 自有 `tool.git`，把拉取、状态/差异检查、提交和推送收敛到一个常规适配器，
使显式挂载的自进化 Agent 能在绑定仓库内完成常规的代码闭环。

该 change 不把 Git 命令解释器暴露给模型，不把 Token 写入 prompt 或 Agent 配置，也不增加
推送前审计或人工确认门槛；新 Agent 的默认只读工具集合仍不自动挂载外部副作用工具。
