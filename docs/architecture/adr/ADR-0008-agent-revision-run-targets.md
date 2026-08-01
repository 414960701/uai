---
kind: adr
id: ADR-0008
status: accepted
date: 2026-08-02
supersedes: ADR-0002 (the Agent Instance decision for the 0.1.x control plane)
---

# ADR-0008：Run 直接选择 Agent 修订

## 背景

`0.1.x` 的 Agent Instance 同时承担了固定 Agent revision、环境标签、启停状态和并发
容量。但当前运行时是单进程本地控制面，环境标签不触发部署，Instance capacity 也不是
独立的调度资源。它给首用流程增加了一个没有实际收益的中间资源。

## 决定

- Run 请求只接受稳定的 `agent_id`，并允许可选的 `agent_revision`。
- 未提供 `agent_revision` 时，控制面在提交时读取该 Agent 的最新 revision；随后 Run
  固定实际解析到的 revision，历史 Run 不随 Agent 后续发布而改变。
- `latest` 是 Agent 上指向某个不可变 revision 的可移动标签，不是历史 revision 的
  `MAX(revision)`。回滚只移动这个标签；继续编辑/发布从全局 revision 序列分配新编号，
  不复用被回滚的编号。
- 提供 `agent_revision` 时，控制面读取并校验对应的不可变 revision；不存在、禁用或
  拓扑无效时 fail closed。
- `0.1.x` 不再把 Instance 作为运行目标、控制面资源、并发信号量或运行上下文。环境标签、
  Instance override 和 ready/stopped 生命周期不再进入新的公共合同。
- 子 Agent mount 继续可以固定自己的 revision；未提供 revision 时，在子调用开始时
  解析子 Agent 的 `latest`。这与一个独立的运行目标资源无关。
- 已有 SQLite 的 `instances` 表和历史 Run JSON 中的 `instance_id` 可以保留作兼容数据，
  但新代码不读取、不创建、不更新，也不在新 Run 中写入。

## 结果

- 首用路径从“Agent → Instance → Run”简化为“Agent → 可选 revision → Run”。
- 版本回滚和审计仍然由不可变 Agent revision 提供，不需要额外 Instance 生命周期。
- 如果未来需要真实部署、容量或 desired/observed state，应以独立 deployment profile 和
  controller ADR 重新引入，而不是恢复当前 Instance 资源。
