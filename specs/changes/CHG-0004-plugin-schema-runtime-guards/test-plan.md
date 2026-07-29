---
kind: test-plan
id: CHG-0004-TEST-PLAN
status: passed
---

# Test plan

- provider、tool、memory、middleware 的有效/无效 config。
- 第三方动态注册 manifest、无效 Schema、未知插件、kind mismatch、missing factory。
- API create/PATCH 拒绝且不产生 revision。
- 原始 Repository 绕过后的 RunManager/Runtime 二次拒绝。
- 工具 required、额外字段、错误类型与 middleware 篡改。
- delegation required、额外字段、错误类型和超长输入。
- disabled memory 零 factory/load/append；不同 retention 各自生效。
- 后端全套、compileall、pip check、JSON/YAML 解析。
