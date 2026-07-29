---
kind: acceptance
id: CHG-0002-ACCEPTANCE
status: passed
---

# Acceptance

- [x] 高级 Agent revision、mount 和插件配置可由真实 API 保存。
- [x] 多 Instance 的创建、停止与重新启用可由真实 API完成。
- [x] 真实 bounded delegation Run 成功并显示 17 条有序持久事件。
- [x] 安全与部署能力不再使用误导性的本地假开关。
- [x] 最终前端与后端全量门禁通过。

2026-07-30 合并终验：`npm run lint`、`npm run typecheck`、production build 与 3 项
SSR/source tests 全部通过；Python 3.9.6 后端 `65 passed`。
