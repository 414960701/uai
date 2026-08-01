---
kind: test-plan
id: CHG-0029-TEST-PLAN
status: complete
---

- 模型/API：验证只接受 `agent_id`，latest 和显式历史 revision 均可运行，未知 revision
  在持久化前失败；latest 回滚指针不取最大 revision，继续发布不复用编号；`instance_id`
  和 `/instances` 不再是新公共路径。
- Runtime：验证 Run、`run.started`、Provider/Middleware/Tool context 使用实际
  `agent_revision`，child mount 留空时使用子 Agent latest，不再带 Instance/environment 身份。
- 前端：验证 RunModal 只含 Agent 与 revision 选择，“最新版本（默认）”为默认项，
  不含“运行实例”导航或 Instance 管理文案。
- 门禁：`python -m pytest backend/tests -q`、`npm run lint`、`npm run typecheck`、
  `npm test`、`git diff --check`。
