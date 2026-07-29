---
kind: test-plan
id: CHG-0002-TEST-PLAN
status: accepted
---

# Test plan

- `npm run lint`、`npm run typecheck`、`npm test` 全部通过。
- 服务端渲染不出现 starter 内容或 hydration mismatch。
- 自动化源合同检查高级配置字段、真实 history 路径和只读能力组件仍存在。
- 真实浏览器发布 Agent rev 2，保存 middleware 与固定 child revision。
- 创建第二个 Instance，验证 revision/environment/capacity，停止后重新启用。
- 通过该 Instance 执行 `delegate:market_analyst ...`，Run 成功并展示从
  `run.started` 到 `run.completed` 的 17 条连续事件。
- 桌面截图确认朴素浅色层级、可辨识焦点和只读状态表达。
