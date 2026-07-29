---
kind: adr
id: ADR-0005
status: proposed
date: 2026-07-30
---

# ADR-0005：以 checkpoint、outbox 和 fencing 实现 at-least-once

## 背景

进程可能在外部调用前后任意位置终止。分布式系统无法仅靠内存 Task 判断调用是否发生，
也不能诚实承诺所有外部系统的 exactly-once。

## 提议

- Run 和 Invocation 使用显式状态机。
- 在数据库事务中提交 checkpoint 与副作用 intent/outbox。
- dispatcher 为每个副作用使用稳定 idempotency key。
- worker lease 带递增 fencing token；旧 worker 的写入被拒绝。
- 可幂等动作允许自动重试；不可幂等动作进入人工确认或失败。
- 恢复语义对外声明为 at-least-once。

## 采用前提

- 完成三类崩溃窗口和旧 worker fencing 测试。
- 定义工具幂等能力声明。
- 定义 checkpoint、outbox 和 lease schema 迁移。
- 明确事件与业务状态的事务边界。

## 不采用的方案

- 仅在应用启动时把所有 `running` Run 重新执行。
- 依赖消息系统“看起来只投递一次”。
- 把幂等责任隐式留给每个工具而不做 capability 声明。
