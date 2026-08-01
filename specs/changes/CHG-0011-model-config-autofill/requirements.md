---
kind: requirements-delta
id: CHG-0011-REQUIREMENTS
status: implemented
---

# Requirements delta

## CFG-007 — Provider/endpoint model autofill

WHEN 用户在 ModelConfig 表单选择 Provider 或已知服务地址
THE SYSTEM SHALL 将 provider、endpoint 与该 Provider manifest 目录中的推荐模型保持一致，
并自动更新模型选择器的当前值。

WHEN 用户输入未登记的自定义服务地址
THE SYSTEM SHALL 保留当前模型，不根据不可靠的 URL 猜测 Provider、协议或凭证。

WHEN 用户编辑已有 ModelConfig 并切换 Provider
THE SYSTEM SHALL 保持现有 Secret 边界，要求用户显式替换或清除凭证；自动带出模型不得
把 Secret 写入浏览器持久化、Agent、事件或 API 响应。
