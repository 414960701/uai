---
kind: design-delta
id: CHG-0003-DESIGN
status: accepted
target: 0.1.x
---

# Design delta

## 预算

每个 Run 建立一个 `root BudgetLedger`。每次 `_execute_agent` 另持有一个 invocation ledger：

```text
root agent:    invocation ledger is root ledger
bounded child: invocation ledger = new BudgetLedger(child.policy)
```

step/tool/token 消耗通过组合预算对象完成。本地与根不是同一对象时先扣本地、再扣根；Run
一旦任一扣减失败即终止，因此不需要补偿已经发生的计数。终态 metrics 保持根账本的兼容
形状；`budget.updated` 额外携带当前 invocation 的本地快照。

`max_steps` 同时由本地循环与本地账本保护；`max_tool_calls`、`token_budget` 使用双账本。
`fail_fast` 继续使用当前执行 Agent 的 policy。

token usage 是 provider 调用后才知道的已发生消耗；即使本地 token 上限先失败，也要更新
根账本，并在失败前发出包含 root/local 快照的 `budget.updated`。

## Timeout

`_delegate` 把取得父本地 child semaphore、mount semaphore、根 lease 和执行 child 的完整
协程放入 `asyncio.wait_for(child.policy.timeout_seconds)`。外层 RunManager 仍用 root
timeout 包裹整个 Runtime，因此实际结束时间是两者先到者。timeout 必须转换为带 child ID
的稳定 RuntimeGuardError，并正常释放所有已取得许可。

## 并发

每个 Agent invocation 创建一个只约束其直接 child 的 semaphore：

```text
effective admission =
  root tree semaphore
  AND parent-invocation child semaphore
  AND (tenant, parent id, parent revision, mount alias) semaphore
```

这不是预先计算的一个整数；三个门分别保护不同共享范围。下一层委派前释放可转让 root
lease，返回模型循环前重新取得，避免根容量为 1 时重入死锁。

## 深度

Runtime 传播 ancestor 允许的绝对最大深度。进入 child 时计算：

```text
child_limit = min(parent_limit, child_absolute_depth + child.policy.max_depth)
```

因此任何 ancestor 的较小上限持续有效，child 的本地 `max_depth=0` 允许其自身执行但禁止
下一层 child。

## 工具范围

Runtime 传播 `Optional[Set[plugin_id]]`：

```text
None = universe / no additional restriction
child_scope = intersect(inherited_scope, mount.allowed_tools)
available = enabled child bindings whose plugin_id is in child_scope
```

交集把 `None` 当全集。工具 definitions 只包含 `available`；执行路径仍使用全部已启用绑定
定位伪造调用，然后在创建工具、middleware 或发事件前再次检查 scope。通过 scope 后继续
执行 child 自身的 `deny` / `confirm` / `auto` 策略，mount 不可升级权限。

范围传播到整个 bounded subtree；后代 mount 的 `null` 只继承，不会恢复全集。
