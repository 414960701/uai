---
kind: test-plan
id: CHG-0006-TEST-PLAN
status: passed
---

# Test plan

- 断言 `.openai/hosting.json` 被 Git 忽略且不再跟踪。
- 断言 `.openai/hosting.example.json` 只有中性 D1/R2 空值，不含 `project_id`。
- 在真实 hosting 文件缺失时运行 lint、typecheck、production build/test。
- 解析 Dockerfile、Compose、JSON 和 YAML，并运行 `git diff --check`。
- 扫描当前树和历史中的维护者账号、本机路径、常见 token 与私钥签名。
- 运行后端全套测试，确认部署元数据变更未影响 Runtime。

## 2026-07-31 结果

- 在临时移走真实 hosting 文件后，lint、typecheck、production build 与 4 项 Node 测试通过。
- 后端 `65 passed in 3.78s`；compileall 与 pip check 通过。
- production-only npm audit 为 0 vulnerabilities；Compose 配置、Shell/Node 语法与
  `git diff --check` 通过。
- 单节点 smoke Run `run_89187dde8d934ffc` succeeded，17 条事件从 1 连续到 17；两个
  容器 healthy，doctor `status=ok`，容器、network、volume 和临时镜像完成清理。
- 当前索引除待删除的旧 hosting 文件外未发现维护者账号、本机路径、token 或私钥签名；
  三个既有历史提交只命中同一个非 Secret Sites 项目 ID。
