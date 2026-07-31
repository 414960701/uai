---
kind: requirements-delta
id: CHG-0010-REQUIREMENTS
status: proposed
target: 0.2
---

# Requirements delta

## UI-003 — 首用流程与前置条件

WHEN 控制台连接到空数据库或用户触发缺少前置资源的操作
THE SYSTEM SHALL 从服务器事实计算当前 SetupStatus，并只提供当前可完成的主操作；禁止用
空下拉框、无解释 disabled 或演示数据代替修复路径。

SetupStatus 至少区分：控制面连接、可用 ModelConfig、可运行 Agent、可选 Instance、Run
目标与最近 Run。Instance 不是直接 Agent Run 的强制前置条件。

## UI-004 — 诚实的身份、能力与 Readiness

WHEN 控制台显示身份、tenant、ready、enforced、degraded、部署或安全能力
THE SYSTEM SHALL 使用服务端返回的事实和 `implemented|partial|planned|unavailable` 成熟度，
并显示关键限制；无认证上下文时不得自称 Admin，environment 标签不得被解释为云部署。

WHEN Agent 或 ModelConfig 不能运行
THE SYSTEM SHALL 返回稳定的问题 code、受影响资源和修复动作，不得只返回布尔值或原始异常。

## UI-005 — 可访问、响应式且可恢复的操作

WHEN 用户使用键盘、390px 窄屏、200% zoom 或辅助技术完成连接、模型配置、Agent 创建和
Run 操作
THE SYSTEM SHALL 保持内容、标签、错误、焦点和主操作可感知且可操作；模态框必须支持
初始焦点、焦点圈闭、Escape 关闭和关闭后焦点恢复。

主视图和资源详情 SHALL 可由 URL 恢复；浏览器前进/后退和刷新不得丢失当前资源上下文。

## RUN-009 — 控制台实时 Run projection

WHEN 控制台观察 active Run
THE SYSTEM SHALL 以持久事件 sequence 为游标消费 SSE，按序投射事件和终态；断线后从最后
确认 sequence 续播。状态轮询只能作为校准或 SSE 不可用时的有界降级。

客户端不得因重复事件重复展示业务结果，也不得在未收到服务器终态时本地伪造成功、失败
或取消终态。

## CFG-005 — ModelConfig 生命周期与并发

WHEN 用户创建或更新 ModelConfig
THE SYSTEM SHALL 支持保存草稿、脱敏连接检查、验证后启用、停用、版本化 CAS 更新和显式
`keep|replace|clear` Secret 动作。

Provider 连接检查 SHALL 通过 UAI Forge 自有 Protocol 和 manifest capability 暴露；检查
结果只能包含稳定 code、时间、延迟和脱敏 endpoint/provider/model 摘要，不得包含 Secret、
请求 body、Provider 原始响应或 prompt。

WHEN 配置被 Agent revision 引用
THE SYSTEM SHALL 返回可分页的引用摘要并阻止破坏性删除；停用或验证失效必须使依赖
Readiness 变为不可运行。

## CFG-006 — 数据库兼容门与未来迁移基线

WHEN Runtime 打开已有数据库
THE SYSTEM SHALL 在任何业务写入前读取 schema version 并验证兼容性；未知新版本、缺失
必需迁移或 ADR-0007 之前的 legacy 配置 SHALL fail closed，并通过 doctor/API 返回备份和
重建指引。

本需求不授权自动迁移旧 CredentialProfile/ModelProfile；未来 schema 变化必须使用递增
迁移、dry-run、备份提示和回滚/前滚证据。

## PROTO-003 — 稳定且不泄密的操作错误

WHEN API 拒绝配置、前置条件、并发更新、权限、连接检查或 Run 操作
THE SYSTEM SHALL 返回版本化 Problem Details：`code`、安全的 `message`、`field_errors`、
`resource`、`retryable`、`remediation` 和 `correlation_id`。

Problem Details SHALL 不回显被拒绝的 Secret、完整配置值、Provider 原始 body、prompt、
工具输出或内部堆栈。前端必须按 code 映射可行动文案，并为未知 code 提供安全降级。
