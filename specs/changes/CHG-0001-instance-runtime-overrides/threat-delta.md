---
kind: threat-delta
id: CHG-0001-THREAT
status: accepted
---

# Threat delta

| 威胁 | 处置 |
|---|---|
| override 注入 system prompt、插件或权限 | 严格 Pydantic allowlist，未知字段 fail closed |
| 用更大预算绕过 definition policy | 每个数值字段取 `min` |
| 关闭 fail-fast 放宽失败语义 | 布尔值取 OR，只能保持或收紧 |
| 浅拷贝污染不可变 revision | dump 后构造新对象并完整 `AgentSpec.model_validate` |
| 明文 Secret 经 override 进入 DB/Event | 持久化前递归拒绝；允许字段本身不含 credential |
| 客户端 metadata 伪造 Instance 环境 | 上下文只由已解析 Instance 和服务端 Run 字段生成 |
