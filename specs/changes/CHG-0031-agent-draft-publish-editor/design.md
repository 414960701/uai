---
kind: design-delta
id: CHG-0031-DESIGN
status: accepted
target: 0.1
---

# Design decisions

1. `AgentRevisionInfo` 是 API 的版本历史合同，包含 `revision`、`status`、`is_latest`、
   `spec`、创建/更新时间和 published 时间；运行核心仍只接收 `AgentSpec`。
2. 新 revision 保存为 `draft`。发布只改变该 revision 的 lifecycle 状态，不创建重复
   快照；回滚只改变 Agent 行上的 latest 指针。下一次保存草稿从当前 latest 内容创建新的
   递增 revision，因此回滚后继续发布不会复用历史编号。
3. `PATCH /agents/{agent_id}` 收敛为保存草稿的现有入口，同时提供显式的
   `POST /agents/{agent_id}/draft` 和 `POST /agents/{agent_id}/publish`；版本历史接口
   返回 `AgentRevisionInfo[]`，回滚返回同一合同。
4. 前端 Agent 编辑器采用“配置表单 + 版本历史 rail”布局。历史 published revision
   可以只读预览，也可以载入当前表单作为新的草稿起点；回滚需要服务端 CAS，成功后表单
   直接显示新的 latest。
5. 旧 Instance 路径、`RunRecord.instance_id` 和兼容性读取说明移除；当前数据库 schema
   版本提升并拒绝无法满足新 revision lifecycle 合同的数据库。
