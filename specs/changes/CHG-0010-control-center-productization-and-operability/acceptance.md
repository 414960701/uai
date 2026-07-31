---
kind: acceptance
id: CHG-0010-ACCEPTANCE
status: pending
---

# Acceptance

- [x] 空数据库总览不显示虚构团队、READY、Admin、cloud 部署或“全部生效”。
- [ ] 首用流程可从连接控制面完成到首个真实 Run，缺前置条件时有原因和修复入口；本轮已用隔离 Provider fixture 完成一次浏览器旅程，但尚未形成可重复的浏览器自动化门禁。
- [x] ModelConfig 支持 draft、脱敏检查、验证后启用、CAS 和 Secret keep/replace/clear。
- [x] 不兼容数据库在写入前 fail closed，doctor 给出备份与重建指引。
- [ ] active Run 通过 SSE sequence 更新，断线续播且 polling 只作降级；代码与后端 SSE 证据已存在，浏览器断线 E2E 尚缺。
- [ ] API 操作错误使用稳定 Problem Details，Secret canary 全输出不泄露；当前已有 API/冲突/输入反例，完整日志、事件、HTML 和未知 code 矩阵尚缺。
- [ ] 控制台资源请求可局部失败；跨 API/tenant/credential 边界不残留旧数据。
- [ ] 核心流程支持 URL 恢复、键盘、390px、200% zoom 和 reduced motion；本轮已人工验证 URL 恢复、390px、Escape/焦点恢复，200% zoom、reduced motion 和自动化证据仍缺。
- [ ] 前端存在真实交互、SSE、错误、焦点和响应式自动化证据，不只做源码字符串断言。
- [ ] 后端、前端、schema compatibility、容器和发布门禁全部通过并更新全局追踪矩阵；本轮容器 smoke 已通过，但发布门禁、真实第三方 Provider、安全泄露矩阵和备份恢复仍未完成。

未勾选条目仍表示当前实现或自动化证据不完整；CHG-0010 在全部剩余条目通过前保持 `pending`。
