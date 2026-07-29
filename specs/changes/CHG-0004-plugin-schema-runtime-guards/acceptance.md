---
kind: acceptance
id: CHG-0004-ACCEPTANCE
status: passed
---

# Acceptance

- [x] 四类 runtime binding config 由动态 manifest Schema 驱动校验。
- [x] 无效配置不能经 API/Repository 保存，也不能经旧数据进入 Run。
- [x] 工具与 delegation 参数在副作用前 fail closed，错误不回显值。
- [x] disabled memory 与不同 retention 配置有自动化证据。
- [x] Python 3.9.6 后端全套通过（2026-07-30：`65 passed`）。
- [x] compileall、pip check 与 JSON/YAML 合同检查通过。
