---
kind: threat-delta
id: CHG-0034-THREATS
status: accepted
target: 0.1
---

- 明文泄漏：secret 仅存在于请求处理和 resolver 局部变量；Pydantic 响应模型、SQLite 查询结果映射和 UI 状态均不包含明文。
- 越权引用：resolver 和所有 CRUD 使用 tenant ID；跨租户 ID 解析按缺失处理。
- 轮换竞态：更新要求 version CAS；旧页面不能覆盖新密文。
- 误删凭证：删除在 Agent revision 引用存在时 fail closed；清除 secret 后资源自动停用。
- 部署密钥：master key 仍属于 bootstrap/Secret Manager 注入，不由本 change 的页面维护；用户提供的真实 token 不进入仓库或自动化。
