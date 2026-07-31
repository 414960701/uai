---
kind: design-delta
id: CHG-0008-DESIGN
status: accepted
target: 0.1.x
superseded_by: CHG-0009
---

# Design delta

> 历史说明：下方“只注册 `openai_compatible`”描述的是 CHG-0008 的验收时点。CHG-0009
> 后续增加了 `anthropic_messages`，并将旧 profile 合同替换为统一 `ModelConfig`；当前
> provider catalog 以 current spec、部署文档和 CHG-0009 为准。

`register_builtins()` 只注册 `openai_compatible` provider。生产 `ModelBinding` 默认指向
该 provider，但实际 Agent 仍必须引用数据库中的 ModelProfile/CredentialProfile；缺失
凭据时继续 fail closed。

需要可重复运行的测试不再污染产品 registry：`backend/tests/test_support.py` 定义
test-only provider 和 topology helper，测试显式把它注册到测试进程。它不被打包为
`uai_forge` provider、不会出现在 `/api/v1/plugins` 或容器 doctor 中。

控制台连接失败只显示 disconnected 空状态。容器 smoke 使用独立新 volume，检查 doctor、
provider API 和各业务配置 API 的空集合，然后清理本次资源；真实模型 API smoke 由已配置
外部 provider 的维护者另行执行。
