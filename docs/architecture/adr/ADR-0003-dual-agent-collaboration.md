---
kind: adr
id: ADR-0003
status: accepted
date: 2026-07-30
---

# ADR-0003：区分 bounded child 与 durable peer

## 背景

“子 Agent”既可能表示一次受限工具调用，也可能表示拥有独立会话的长期协作者。用同一
运行机制承载两者，会使预算、取消、权限和恢复语义含糊。

## 决定

提供两种明确模式：

1. `bounded_nested`：父 Run 内的 agent-as-tool，继承根预算和取消，返回结构化结果。
2. `durable_peer`：独立 Session/Run，通过持久 inbox 和版本化消息协作。

Mount 必须声明模式。未声明的 `0.1.0 ChildMount` 按 `bounded_nested` 解释；未来升级不得
自动变成 peer。

## 结果

- 调用方可以根据生命周期选择正确语义。
- durable peer 可以跨进程恢复，bounded child 保持简单。
- 需要 Team、Inbox、PeerMessage、独立权限和 workspace sharing policy。
- UI 必须用不同图形和状态展示两种关系。
