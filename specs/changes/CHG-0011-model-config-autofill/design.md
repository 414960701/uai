---
kind: design
id: CHG-0011-DESIGN
status: implemented
---

# Design

## Preset contract

每个常用服务地址 preset 包含：

- `value`：规范化服务地址；
- `provider`：UAI Forge Provider manifest ID；
- `defaultModel`：该服务的推荐模型 ID；
- `label`：仅用于展示的厂商名称。

Provider 选择沿用 manifest/catalog 的默认模型。Endpoint 选择优先使用 preset 的
`defaultModel`；手动输入不匹配 preset 的地址只更新 `baseUrl` 并保留当前模型。这样既
减少首用配置步骤，也不会把任意 hostname 当成可信 Provider 发现机制。

## Security and compatibility

该变更只影响前端表单状态，不改变 `ModelConfig`、Secret 加密、Provider 协议或数据库
合同。已有配置加载后仍保留其明确的 `model`；只有用户主动选择 Provider/已知 preset
才触发模型更新。切换 Provider 时继续使用显式 `keep|replace|clear` Secret action。
