---
kind: change-proposal
id: CHG-0031
status: accepted
target: 0.1
implementation_status: complete
requirements:
  - CORE-009
  - UI-009
---

# Agent 草稿/发布生命周期编辑器

当前 Agent 编辑器保存后直接创建不可变修订，操作者无法在发布前持续保存草稿、查看
版本状态或从历史版本继续发布。本变更把版本控制面收敛为一个可见的编辑闭环：草稿、
发布、latest、回滚和继续发布都由控制面持久化，前端只展示服务端返回的版本事实。

本变更是对 ADR-0008 中“仅保留旧实例/旧 Run 数据兼容读取”的明确替代：当前基线不再
读取或暴露旧 Instance 字段，数据库按新的 Agent revision lifecycle 合同运行；旧数据库
需要备份后重建，不做静默兼容。

## 范围

- Agent revision 增加 `draft` / `published` 状态和 published 时间。
- 草稿保存、发布、版本历史、回滚和继续发布 API。
- Agent 编辑器显示当前状态、latest 标签、历史版本和操作结果。
- Run 和 child mount 的版本选择统一显示草稿/发布状态；留空继续跟随 latest。

## 非目标

- 不引入 Deployment、Instance、容量调度或 RBAC。
- 不实现 revision diff 算法；历史版本可以加载到编辑器作为新的草稿起点。
- 不迁移旧 Instance 表或历史 Run JSON。
