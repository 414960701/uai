---
kind: design-delta
id: CHG-0015-DESIGN
status: proposed
target: 0.1
---

# 计划模式设计

1. `execution_mode` 是 UAI Forge 核心枚举，默认 `execute`；不复用 thinking mode，避免把
   “是否展示计划”和“模型是否使用推理参数”混为一谈。
2. Runtime 在 `plan` 模式构造模型请求时使用空工具定义；公开阶段先发送“计划模式：只生成
   计划，不调用工具或子 Agent”。工具调用异常结果不会进入执行入口。
3. Run metrics、`run.started`、`model.started` 和前端 Run inspector 保留稳定模式值；不保存
   prompt、reasoning 或 Provider 对象。
4. 计划模式仍是普通 Run，沿用现有预算、超时、取消、事件历史和 Trace，不创建第二个计划
   事实源。
