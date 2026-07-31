---
kind: task-delta
id: CHG-0010-TASKS
status: proposed
---

# Tasks

## Wave A — 事实一致与首用闭环

- [x] `TASK-023` 对 current spec、README、部署和 CHG-0008/0009 关系做 reconciliation，清除
  当前基线中的单 Provider、旧 profile 和失效 E2E 证据措辞。
- [x] `TASK-024` 定义 SetupStatus、CapabilityStatus、ReadinessIssue 与 Problem Details 合同及
  正反 Schema 样例。
- [x] `TASK-025` 实现计算型 setup/readiness API；控制台空库总览和所有主操作接入统一前置门。
- [x] `TASK-026` 移除硬编码 Admin、READY、“全部生效”和 cloud 部署暗示，改为服务端事实。

## Wave B — ModelConfig 可靠生命周期

- [ ] `TASK-027` 扩展 Provider manifest/Protocol/TCK 的 connection check、UI hints 和目录版本。
  内置 manifest/Protocol/检查及内部 Provider connection-check TCK 已实现；第三方 adapter TCK、真实网络/timeout/取消故障矩阵仍待补齐。
- [x] `TASK-028` 为 ModelConfig 增加 version/CAS、lifecycle、verification 和 Secret action。
- [x] `TASK-029` 实现内置 OpenAI/Anthropic 脱敏检查、引用摘要和 draft/test/enable UI。
- [x] `TASK-030` 增加 endpoint 合同、部署策略和 SSRF 正反测试。

## Wave C — Run 实时与错误恢复

- [x] `TASK-031` 建立共享 Problem Details 映射器和类型化前端 API client。
- [x] `TASK-032` 将全局 Promise.all 改为资源级 ready/stale/error，并验证身份边界切换清空。
- [x] `TASK-033` 实现 history + SSE cursor + reducer + reconnect；polling 仅作 degraded fallback。
- [x] `TASK-034` 让 cancel 和终态只由服务器响应/事件确认，增加重复事件与断线回归。

## Wave D — 可访问性与可维护性

- [ ] `TASK-035` 拆分 control-center feature modules、共享 Dialog/Prerequisite/Readiness 组件。
- [x] `TASK-036` 建立 URL 可恢复的主视图和资源详情。
- [x] `TASK-037` 将 Agent 创建改为基础/能力/策略/Review 分步流程。
- [x] `TASK-038` 完成字体、焦点、错误关联、390px、200% zoom、reduced-motion 和键盘修复；真实浏览器验收仍未完成。

## Wave E — 升级与发布证据

- [x] `TASK-039` 增加 schema_meta、legacy 检测、doctor 只读诊断和备份/重建指引。
- [x] `TASK-040` 增加 `make verify` 与机器可读 evidence summary，不绑定托管平台 workflow。
  `make verify` 已增加，并生成 `artifacts/evidence-summary.json`；文件由 `.gitignore` 排除，避免把本地凭据/环境元数据带入版本库。
- [ ] `TASK-041` 执行全套后端、前端、浏览器、容器、安全和泄露测试，更新全局追踪矩阵。
  后端、前端、Compose 配置和本轮隔离容器 smoke 均通过；本轮也用隔离 Provider fixture 完成一次真实浏览器首用/Run/390px/URL/焦点旅程，但浏览器自动化、真实第三方 Provider、完整日志/HTML/事件泄露矩阵和备份恢复演练仍需在发布前复跑。
