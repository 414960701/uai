---
kind: test-plan
id: CHG-0001-TEST-PLAN
status: accepted
---

# Test plan

- API 接受已声明的 policy override，并在 OpenAPI 中暴露显式 Schema。
- API 拒绝未知顶层/策略字段、prompt/model/tools/children 和明文 credential。
- definition 上限较小或 override 上限较小时，effective policy 均取较小值并实际限制 Run。
- 运行前后读取同一 revision，JSON 完全不变。
- provider metadata、`run.started` 和终态 metrics 包含服务端 Instance 上下文。
- 直接 Agent Run 继续成功且不获得伪造的 Instance 身份。
- 全量运行 `python -m pytest backend/tests -q`。
