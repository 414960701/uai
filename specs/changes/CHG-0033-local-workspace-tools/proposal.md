---
kind: change-proposal
id: CHG-0033-PROPOSAL
status: in_progress
target: 0.1
---

# 本地开发工作区工具

当前自进化 Agent 只能调用远程只读工具和时间/计算工具，无法检查本地源码、应用小范围补丁或运行测试，因此“成功”不代表真实完成了代码进化。

本 change 为本地单进程开发部署增加显式 opt-in 的 `tool.workspace`。它不改变默认 Agent 能力，不替代生产级 WorkspaceProvider，也不把 Docker socket、宿主环境变量或任意 Shell 暴露给模型。
