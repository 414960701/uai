# Threat delta

- **T1 明文 AK 泄漏**：写入前加密；响应只有 mask；模型绑定和事件不携带 secret；测试扫描
  response/SQLite/Run。
- **T2 跨租户读取**：所有仓储查询使用 `(tenant_id, id)`；API 使用 `X-Tenant-ID` 校验；
  测试验证其他 tenant 得到 404。
- **T3 失效凭据继续调用**：disabled/missing profile 在保存校验和运行解析阶段 fail closed。
- **T4 删除仍被使用的配置**：数据库层阻止删除 CredentialProfile，API 检查 Agent 引用的
  ModelProfile，返回 409。
- **T5 配置竞态覆盖**：RuntimeConfig 使用版本 CAS；旧版本更新返回 409。

master key 生命周期、RBAC、审计不可抵赖性和 Secret Manager 轮换仍是后续部署工作，不在
0.1.x 单进程基线内虚假承诺。
