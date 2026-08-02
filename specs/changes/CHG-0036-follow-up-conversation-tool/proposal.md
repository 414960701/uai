---
kind: change-proposal
id: CHG-0036-PROPOSAL
status: in_progress
target: 0.1
---

# Follow-up Conversation 工具

为自进化 Agent 增加一个普通的 UAI Forge 工具，使 Agent 可以把下一阶段任务提交为新的
conversation/Run。工具复用 RunManager 的正常合同，不通过 HTTP、数据库或隐藏 prompt 指令
伪造新对话。
