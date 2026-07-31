---
kind: threat-delta
id: CHG-0010-THREAT
status: proposed
---

# Threat delta

| 威胁 | 设计处置 | 剩余边界 |
|---|---|---|
| UI 把未认证用户显示为 Admin | 身份和 tenant 只渲染服务端事实；0.1 显示未认证本地操作者 | OIDC/RBAC 仍属 0.4 |
| API base/tenant 切换后展示旧租户数据 | 边界变化先清空；只有同边界瞬时错误可保留 stale 数据 | 可信 tenant 仍需身份绑定 |
| 连接检查泄露 Secret/Provider body | 自有脱敏结果合同、响应上限、allowlist error mapping、canary 测试 | 第三方 adapter 需通过 TCK |
| 自定义 endpoint 触发 SSRF | URL 规范化、scheme/地址策略、DNS/IP 防护、egress policy | 本地开发例外必须显式；公网部署需网络层控制 |
| 并发检查覆盖新配置 | 外部调用不持事务；提交 verification 时用 expected_version CAS | 检查可能浪费一次外部请求，但不覆盖新状态 |
| Secret clear/Provider 切换保留不必要密文 | 显式 keep/replace/clear；切换时降级 draft 并提示清理 | 备份中的旧密文按保留策略处理 |
| Problem Details 回显输入或堆栈 | input-free mapper、稳定 code、未知异常安全降级 | 服务端日志仍需独立脱敏门禁 |
| SSE 重放导致重复展示/跨租户读取 | sequence 去重、ownership 查询、断线 cursor 不携带权限 | 身份绑定 tenant 仍未实现 |
| schema 不兼容时部分写入 | 启动写入前 compatibility gate；migration transaction | 备份/恢复仍需部署演练 |
| 静态模型目录误导或供应链污染 | 显示来源、版本和更新时间；目录不作为运行时配置 | 来源真实性需 release review |

本变更不降低现有 fail-closed 规则，也不把 UI 提示当作安全边界。
