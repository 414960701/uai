---
kind: threat-delta
id: CHG-0031-THREAT
status: accepted
---

- 草稿可以被运行，因此 Run 提交前继续执行已有的模型配置、启用状态和拓扑 fail-closed
  校验；版本状态不替代 readiness 校验。
- 发布、回滚和保存草稿都使用 latest revision CAS，防止两个编辑者静默覆盖状态。
- 版本历史只返回 Agent 配置引用和非密钥字段；现有密钥引用/明文拒绝规则不变。
- 删除旧兼容读取后，旧数据库启动失败并给出备份重建 remediation，不尝试猜测旧字段语义。
