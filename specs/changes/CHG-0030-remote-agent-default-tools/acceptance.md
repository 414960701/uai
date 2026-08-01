---
kind: acceptance
id: CHG-0030-ACCEPTANCE
status: accepted
---

- [x] Web Search、Web Fetch、Web JSON 和 Web RSS 可在内置 registry 中发现、按 Schema 调用，并有边界回归测试。
- [x] Web 工具只读、公网 HTTPS、有界、重定向复核且不把外部页面当作指令。
- [x] 新建 Agent 默认显示并提交六个基础工具；显式空列表仍可创建无工具 Agent。
- [x] 新建 Agent 默认预算和子 Agent 并发值在 API、Pydantic 和 UI 一致。
- [x] 2026-08-02 最新源码浏览器 smoke：主导航、连接/刷新、模型配置 draft→check→enable、四步 Agent 向导、六个工具往返、sandbox 显式加入/移除、策略、草稿/发布/回滚、Run、Plan、Trace 和关闭按钮均通过。
- [x] 后端、前端、浏览器 smoke 和仓库发布门禁通过；浏览器证据见 `docs/testing/manual-browser-2026-08-02.md`。
