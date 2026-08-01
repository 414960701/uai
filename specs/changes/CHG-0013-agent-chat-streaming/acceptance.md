---
kind: acceptance
id: CHG-0013-ACCEPTANCE
status: passed
---

- [x] 普通无工具 Agent 对话在 `run.completed` 前显示模型增量正文和公开阶段。
- [x] 刷新或 SSE 重连后，聊天正文可由 `model.delta` 历史恢复且不重复。
- [x] 工具调用、不支持流式 Provider、失败和取消路径保持兼容。
- [x] 协作拓扑具备 React Flow 节点、边、缩放、适配视图、MiniMap 和选择交互。
- [x] 运行记录可按事件类别/错误筛选，展示 trace/span 关系、耗时、预算和完整事件详情。
- [x] `model.delta`、阶段事件和 Trace 不泄漏密钥、Provider 对象、原始请求配置或隐藏思考。
- [x] 前后端门禁和真实模型 smoke 通过。

验收证据（2026-08-01）：`backend/tests` 117 项通过；`npm run lint`、
`npm run typecheck`、`npm test` 通过。真实模型 Run
`run_fecd37873f49423e` 产生 17 条有序事件，其中 6 条 `model.delta`，全部位于
`run.completed` 之前，最终正文为“流式输出已连通”，并携带
`trace_run_fecd37873f49423e`、根 span 与模型 span 关联。浏览器 smoke 验证了聊天阶段、
实时正文、Trace 统计/模型筛选、React Flow 节点/Controls/MiniMap、扩展中心中文文案和
控制台无 error；旧事件无 trace 字段时显示兼容提示“历史事件未携带”。
