---
kind: test-plan
id: CHG-0017-TEST-PLAN
status: executed
---

# Test plan

- 运行时：带天气快速路径标签且缺少地点时不调用模型/工具/子 Agent，仍产生完整终态事件。
- 运行时：带地点、无标签、未知标签和普通 Agent 均保留既有执行路径。
- 运行时：模型、工具、委派和 Agent 完成/失败事件带非负 `duration_ms`，事件中不出现凭证或
  prompt。
- 前端：Run inspector 和运行记录 Trace 展示阶段耗时、进行中计时、Trace/span/parent 关系，
  并保持公开思考摘要安全边界。
- 回归：既有流式、计划、工具、委派、失败、取消和历史事件回放测试保持通过。

必跑命令：

```bash
npm run lint
npm run typecheck
npm test
python -m pytest backend/tests -q
```

执行证据（2026-08-01）：`124 passed`；`npm run lint`、`npm run typecheck`、`npm test` 通过；
Docker backend/frontend 构建并健康启动；浏览器确认流式运行中的公开阶段与运行记录 Trace；
取消路径确认终态不再显示旧的“进行中”提示。
