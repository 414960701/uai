---
kind: requirements-delta
id: CHG-0031-REQUIREMENTS
status: accepted
target: 0.1
---

### CORE-009 — Agent revision lifecycle

WHEN Agent 定义被创建或编辑保存
THE SYSTEM SHALL 创建一个不可变 revision，并将其标记为 `draft`；当前 Agent 的
`latest` 指针 SHALL 指向该 revision。

WHEN 操作者发布当前 Agent 草稿
THE SYSTEM SHALL 将该 revision 标记为 `published`，保留其 revision 编号和快照内容，
并保持 `latest` 指向它；发布 SHALL 不覆盖或删除任何历史 revision。

WHEN 操作者回滚到一个历史 revision
THE SYSTEM SHALL 只移动 `latest` 指针到目标 revision，目标快照和其 draft/published
状态 SHALL 保持可审计；后续从该版本继续编辑 SHALL 分配新的单调递增 revision 编号。

WHEN 操作者携带过期的 latest revision 保存草稿、发布或回滚
THE SYSTEM SHALL 返回冲突并不得写入部分状态。

WHEN 控制面打开数据库
THE SYSTEM SHALL 使用当前 lifecycle schema；旧 Instance 表、旧 Run `instance_id`
或旧 Agent lifecycle 字段 SHALL 不进入新的读取路径，无法满足当前 schema 时明确要求
备份并重建。

### UI-009 — 草稿/发布状态编辑器

WHEN Agent 构建者打开 Agent 编辑器
THE SYSTEM SHALL 同屏显示当前草稿/发布状态、latest 标签、当前 revision 和历史版本列表。

THE SYSTEM SHALL 提供“保存草稿”“发布草稿”“回滚到此版本”和“从此版本继续编辑”动作，
并在每次动作后明确显示服务端返回的 revision、状态和冲突提示。

WHEN 构建者编辑子 Agent mount
THE SYSTEM SHALL 提供该子 Agent 的草稿/发布版本选择；不选择时显示“latest（默认）”。

WHEN 构建者发起 Run
THE SYSTEM SHALL 提供当前 Agent 的草稿/发布版本选择；不选择时提交空 revision，
由控制面在提交时解析 latest。
