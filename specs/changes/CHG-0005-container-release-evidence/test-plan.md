---
kind: test-plan
id: CHG-0005-TEST-PLAN
status: passed
---

# Test plan

- `docker compose config --quiet`。
- 从干净/可复用 cache 构建 Python 与 Web 镜像。
- 后端与前端容器均为 `running (healthy)`。
- 容器内 `uai-forge doctor` 返回数据库、Agent、插件、provider 与 `status=ok`。
- 新数据库的 Agent、Instance、凭据、模型档和运行配置查询均为空。
- 脚本结束后测试 project 的容器、网络与 volume 被清理。
- `npm audit --omit=dev --audit-level=high` 必须通过；完整 `npm audit` 用于审查开发链剩余项。
- 后端全套、前端 lint/typecheck/build/source tests、JSON/YAML 合同检查。

## 2026-07-30 结果

- 后端 `65 passed`；compileall 与 pip check 通过。
- `npm ci`、`npm ls --all`、production-only audit、lint、typecheck、production build
  与 3 项 Node 测试通过。
- Web 运行镜像裁剪后审计 192 个 production package 为 0 vulnerabilities，且不含
  ESLint/Drizzle Kit 开发工具。
- Compose smoke 两个容器 healthy，doctor `status=ok` 且 provider 仅为
  `openai_compatible`，结束后容器、network、volume 均不存在。
- 碰撞负例验证：预先存在的同名 volume 被拒绝，原 volume 保持完好；默认 Compose
  host ports 均解析为 `127.0.0.1`。
- 9 个 JSON、18 个 YAML（21 documents）可解析，34 份 change Markdown 的 ID 一致。
