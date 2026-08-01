---
kind: adr
id: ADR-0009
status: accepted
date: 2026-08-02
supersedes: ADR-0008 (Agent revision lifecycle and compatibility clauses)
---

# ADR-0009：Agent 修订的草稿/发布生命周期

## 背景

ADR-0008 已经把 Run 目标简化为 Agent + 可选 revision，但编辑器仍把每次保存直接当作
发布，无法表达发布前的工作状态。旧 Instance/Run 兼容读取也会让新生命周期继续背负
已经删除的资源语义。

## 决定

- Agent revision 是不可变快照，并有 `draft` 或 `published` 生命周期状态。
- 保存创建 draft；发布只把当前 draft 标记为 published；两者都保留 revision 快照。
- Agent 的 latest 是可移动指针，可以指向 draft 或 published revision；Run 未显式选择时
  在提交时解析该指针并固定实际 revision。
- 回滚只移动 latest，不删除、不重写、不复用历史 revision；从回滚目标继续保存会创建
  新的递增 draft。
- 发布、回滚和保存草稿都需要 latest revision 的乐观并发校验。
- 当前基线不读取旧 Instance 表、旧 Run `instance_id` 或旧 Agent lifecycle 字段；不满足
  当前 schema 的数据库必须备份并重建。
- 子 Agent mount 的 revision 仍可显式固定；为空时跟随子 Agent latest。

## 结果

Agent 编辑器能清楚区分“正在编辑”和“已经发布”，调用者可以选择任意可用版本；版本
审计和回滚不再依赖没有运行时价值的 Instance 资源。旧数据库不被静默解释，减少错误迁移
和错误调用的风险。
