---
kind: test-plan
id: CHG-0011-TEST-PLAN
status: implemented
---

| 场景 | 证据 |
|---|---|
| Provider 和 endpoint preset 都声明默认模型 | `tests/rendered-html.test.mjs::model configuration selection auto-fills model from provider or known endpoint` |
| 已知服务地址显示自动带出提示并接入表单回调 | 同上，配合 `npm run lint` 与 `npm run typecheck` |
| 自定义地址不覆盖当前模型 | `app/control-center.tsx::ModelConfigsView.selectEndpoint` 的 `providerChanged` 分支 |
| 统一配置、Secret 和 API 兼容性未回退 | `python -m pytest backend/tests -q`、`make verify` |
