---
kind: change-proposal
id: CHG-0010
status: proposed
target: 0.2
date: 2026-08-01
implementation_status: partial
requirements:
  - UI-003
  - UI-004
  - UI-005
  - RUN-009
  - CFG-005
  - CFG-006
  - PROTO-003
---

# 控制台产品化与可运维操作闭环

## 背景

CHG-0008 已移除产品 Mock、seed 和伪造业务数据，CHG-0009 已把 Provider 凭证与模型档统一
为真实 `ModelConfig`。后端事实源已经改变，但控制台仍保留“运行研究团队”“READY”等
演示叙事，并允许用户在缺少前置资源时进入空表单。Run 页面也没有消费后端现有 SSE，
ModelConfig 缺少版本冲突、连接验证和显式 Secret 轮换语义。

## 目标

- 让空库用户沿“连接 → 模型连接 → Agent → 可选 Instance → Run”完成首个真实任务。
- 所有能力、身份、ready 和部署状态都由服务器事实或明确的 maturity 状态驱动。
- 让模型连接支持草稿、脱敏验证、并发更新和显式 Secret 生命周期。
- 让运行视图通过 SSE sequence 持续更新，并在断线后恢复。
- 建立稳定、可行动、不会泄露输入的错误合同。
- 建立 schema compatibility gate、可访问性和真实浏览器流程证据。

## 非目标

- 不在本变更实现 checkpoint、outbox、lease/fencing 或崩溃续跑。
- 不实现 OIDC/RBAC、可信 tenant identity 或生产级多租户。
- 不引入 Provider SDK/HTTP 类型到核心合同。
- 不重新加入特定托管平台 workflow；发布门禁保持平台无关。
- 不自动迁移 ADR-0007 明确要求重建的旧 CredentialProfile/ModelProfile 数据。

## 原则

1. 先修复错误可见状态，再增加新控件。
2. 前置条件由服务器诊断，前端只负责解释和导航。
3. 验证操作可以失败并保存草稿，但失败不得被显示为 ready。
4. 同一连接的瞬时读取失败可展示带 stale 标记的最后成功数据；身份、tenant 或 API base
   改变时必须先清空，防止跨边界残留。
5. 所有新增 Provider 扩展能力先更新自有 manifest/Protocol/TCK，再实现适配器。

## 交付形态

本目录先冻结需求、设计、任务、兼容性、安全和测试计划。当前状态为 `proposed`，不得在
产品文案中把尚未通过验收的 change 宣称为完整交付。

## 当前工作树实现说明（2026-08-01）

当前工作树已落地 SetupStatus/CapabilityStatus/Readiness、ModelConfig v2 生命周期与 CAS、
Provider connection check、Problem Details、schema compatibility gate、SSE cursor
projection、资源级 stale/error、URL/焦点/响应式修复，以及对应后端和 SSR/source 门禁。
CHG-0010 仍保持 `proposed`，因为真实浏览器首用/断线/键盘/390px/200% zoom 证据、第三方
Provider TCK、失败 migration/备份恢复演练和全输出泄露矩阵尚未齐备；这些缺口见
`tasks.md`、`acceptance.md` 与全局 `specs/traceability.yaml`。
