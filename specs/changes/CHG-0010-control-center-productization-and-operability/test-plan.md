---
kind: test-plan
id: CHG-0010-TEST-PLAN
status: proposed
---

# Test plan

## 合同与后端

- SetupStatus/Readiness 的空库、缺配置、停用配置、插件缺失、拓扑非法和可运行正例。
- Problem Details Schema、未知 code 降级和所有 input-free/secret-free 反例。
- ModelConfig create/update/secret replace/clear/keep、CAS 冲突和引用摘要。
- Provider connection check 的 local/remote/unsupported、timeout、取消、网络失败和响应大小上限。
- endpoint scheme、回环/私网策略、DNS/IP 重绑定夹具和本地开发显式例外。
- schema_meta 的新库、当前版本、legacy profile、未知高版本、失败 migration 和 doctor 只读路径。
- Secret canary 不得出现在 API、Problem Details、事件、日志、异常、HTML 或测试快照。

## 前端组件与集成

- 每种 ResourceState：loading、ready、stale-with-data、terminal error。
- API base、credential 或 tenant 变化先清空旧资源；同边界瞬时失败保留 stale 数据。
- PrerequisiteGate 的原因、修复目标、返回上下文和无空 select 断言。
- Dialog 的初始焦点、Tab/Shift+Tab 圈闭、Escape、关闭后焦点恢复。
- ModelConfig 的 draft/test/enable、CAS 冲突比较、Secret 字段提交后清空。
- Agent 分步表单的前后导航、Review、字段错误和 readiness。
- SSE reducer 对 sequence 去重、乱序拒绝、reconnect cursor、终态和 degraded polling。

## 浏览器关键旅程

1. 断线 → 配置连接 → 空库首用清单。
2. 创建 ModelConfig 草稿 → 连接检查失败 → 修复 → 验证并启用。
3. 创建最小 Agent → readiness 通过 → 直接 Run。
4. 创建 Instance → revision pin → Instance Run。
5. active Run 事件连续到终态；中途断开并从最后 sequence 续播。
6. 取消 Run，UI 等待服务器确认且不提前伪造终态。
7. 一个次要资源接口失败时，其余资源保持可用并标 stale/partial。
8. 两个客户端并发编辑 ModelConfig，旧 version 获得 409 和比较入口。
9. 390px、720px、桌面和 200% zoom；无内容/操作丢失。
10. 仅键盘完成连接、模型配置、Agent 创建和 Run；运行 axe 或等价自动规则，并保留人工
    读序、文案、状态变化复核。

## 发布与回归

```bash
.venv/bin/python -m pytest backend/tests -q
npm run lint
npm run typecheck
npm test
make verify
make container-smoke
```

真实 Provider 在线检查使用隔离、低权限、低额度账号并作为显式 release/eval 门；确定性
门禁使用测试边界 adapter，不把测试 Provider 注册进产品 catalog。

## 失败注入

- 六个首屏接口中的任一接口超时/401/422/500。
- SSE 在 history 与 live 注册窗口断开、重复最后事件、慢客户端断开。
- Provider 在 DNS、TLS、401、429、5xx、超时、超大响应和无效 JSON 下失败。
- ModelConfig 外部检查完成前被另一请求更新。
- migration transaction 中途失败和只读/磁盘满数据库。

测试成功只证明上述范围，不证明分布式恢复、OIDC/RBAC、插件隔离或公网 egress 安全已经完成。
