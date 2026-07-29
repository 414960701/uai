---
kind: normative
id: ARCH-TESTING
status: accepted
version: 1.0.0
last_reviewed: 2026-07-30
---

# 测试策略

## 原则

1. 需求、协议和状态不变量优先于代码覆盖率。
2. 主 CI 使用 deterministic provider 和受控工具，不把 LLM 文本质量当单测。
3. 每个 `SHALL` 至少映射一个可重复的自动化证据。
4. 恢复、幂等、取消、权限和租户边界必须有负向及故障测试。
5. 同一个实现不能同时生成规范和唯一验收测试后自证正确。

## 分层

| 层 | 目标 | 当前证据 | 后续必需 |
|---|---|---|---|
| Model/Schema | Pydantic、JSON Schema、状态转换 | Agent/Binding 校验 | JSON Schema 实例、向后兼容测试 |
| Unit | budget、图、工具、registry | `backend/tests/test_*.py` | Policy、checkpoint reducer、peer message |
| Adapter contract | 所有实现遵守自有 Protocol | 部分 built-in 测试 | Storage/Bus/Provider/Workspace TCK |
| Integration | API + SQLite + runtime + event | FastAPI TestClient、真实 SQLite | Postgres、queue、outbox、migration |
| Frontend | SSR、类型、lint、真实连接状态 | Node SSR test、lint、typecheck | 浏览器交互与无障碍 E2E |
| Recovery/chaos | 崩溃、重投、lease、取消 | 无 | kill worker、重复 delivery、网络分区 |
| Security | tenant、Secret、policy、插件 | 基础 tenant 和协议拒绝 | OIDC/RBAC、approval、SSRF、泄露测试 |
| Model eval | 任务质量和回归 | 无稳定套件 | nightly/release，和确定性 CI 分离 |

## `0.1.0` 门禁

```bash
.venv/bin/python -m pytest backend/tests -q
npm run lint
npm run typecheck
npm test
```

这些命令证明当前 Python、TypeScript、SSR 和构建基线，不证明：

- worker 崩溃恢复；
- 分布式消息投递；
- PostgreSQL/Redis 兼容；
- OIDC/RBAC；
- 插件隔离；
- 真实模型回答质量。

## 关键不变量测试

### Agent 与修订

- 更新需要 `expected_revision`，陈旧 revision 返回冲突。
- 历史 revision 不因最新定义更新而改变。
- Instance 和 mount 钉住不存在的 revision 时拒绝运行。

### Bounded nested call

- 静态 mount 环拒绝执行。
- 图验证必须沿每条 mount 实际钉住的 revision 遍历；覆盖“旧 revision 无环、latest 有环”
  及相反方向。
- 动态 depth、总 step、tool call、token、timeout 和并发限制覆盖整棵调用树。
- 三层委派在根并发为 1 时应顺序完成，不得重入同一 semaphore 死锁。
- 父 Run 取消必须取消正在进行的 bounded child。
- child 不能得到父未授予的工具、Secret 或 workspace。

### Durable peer

状态为 `Specified`，实现前先写失败测试：

- peer 有独立 Session、Run、checkpoint 和 inbox offset。
- 重复消息按去重键只处理一次业务结果。
- sender/recipient/tenant 不匹配时 fail closed。
- 父 Run 完成不隐式终止 peer；取消按 Team policy 传播。

### 可恢复执行

实现前先建立下列故障夹具：

1. 模型完成后、checkpoint 前 kill worker。
2. outbox 写入后、外部调用前 kill worker。
3. 外部调用成功后、结果提交前 kill worker。
4. lease 过期后旧 worker 恢复写入。
5. cancel 与 terminal result 并发。

验收重点不是“最终成功”，而是无非法状态转换、无重复不可幂等副作用、fencing 拒绝旧
worker、事件顺序可解释。

## 插件兼容测试套件

每种插件实现都必须通过通用 TCK：

- manifest JSON Schema。
- core/protocol 版本范围。
- config 默认值、未知字段和 SecretRef。
- timeout、取消和异常映射。
- tenant/context 传播。
- 状态 schema 与逐版本迁移。
- capability 声明与实际行为一致。
- 安全/权限 hook 失败时 fail closed。
- observability hook 失败时标记 degraded。

未知插件不得通过“导入成功”替代 TCK。

## API 与事件合同

- FastAPI OpenAPI 与冻结示例做兼容 diff。
- JSON Schema 使用 draft 2020-12 validator 校验正反样例。
- 当前 Run Event 与目标 Event Envelope 分别测试，不能混称同一版本。
- 新增可选字段允许；删除/重命名/新增 required 字段触发主版本检查失败。
- SSE 重连从 `after_sequence` 继续，不能重复交付已确认的 UI 事件。
- 慢订阅者 queue 满时应断开并依靠持久日志追赶，不能让已持久化事件发布或 Run 失败。

## 前端验证

- lint、typecheck、production build、SSR。
- Live/demo/connecting 三种状态可区分，API 错误不能伪装成 live。
- API key 仅存在当前页面内存，输入为 password 类型。
- Agent 创建、Run 发起、取消和终态轮询走真实 API fixture。
- 键盘导航、焦点、label、颜色对比和窄屏布局。

Sites 发布成功只证明前端制品可访问；仍需单独验证部署页面连接到目标 Python API。

## 测试数据和敏感信息

- 使用显式假 Secret，如 `test-secret-must-not-appear`，并断言所有输出中不存在。
- 测试不读取开发者真实环境凭据；真实 provider eval 使用隔离的低权限账户。
- 时间、ID、重试和并发使用可控制 clock/ID/fake adapter，减少偶发失败。
- SQLite/Postgres contract suite 使用相同数据集和断言。

## 发布证据

`specs/traceability.yaml` 是机器可读索引；它引用测试 node ID、合同和实现位置。发布时保存：

- 命令与退出码；
- core、协议、schema、插件版本；
- migration dry-run/rollback；
- security 和 recovery 场景；
- 已知未覆盖项。

“测试通过”只对列出的范围有效，不能外推到未执行的部署或故障模式。
