---
kind: acceptance
id: CHG-0006-ACCEPTANCE
status: passed
---

# Acceptance

- [x] 当前待发布树不再包含维护者个人 Sites `project_id`。
- [x] 本地真实 hosting 文件仍保留且被 Git/Docker 忽略。
- [x] 干净 checkout 无 hosting 文件时前端门禁通过。
- [x] `.github/workflows/ci.yml` 保留并继续定义完整 CI。
- [x] 当前树除已处理 hosting 文件外无账号、本机路径或凭据签名发现。
- [x] GitHub Actions 在本变更推送后验证通过。

## 本地验收证据（2026-07-31）

- 前端：无真实 hosting 文件的 lint、typecheck、production build 与 4 项 Node 测试通过。
- 后端：`65 passed in 3.78s`，compileall 与 pip check 通过。
- 依赖与配置：production audit 为 0 vulnerabilities；Compose、Shell/Node 语法和
  `git diff --check` 通过。
- 容器：Run `run_89187dde8d934ffc` succeeded，17 条连续事件，双容器 healthy，doctor
  正常，所有测试容器、network、volume 和临时镜像均已清理。
- 扫描：当前索引只保留中性 hosting 示例；历史命中仅为已公开的非 Secret Sites ID，
  未发现真实凭据、私钥、本机绝对路径、数据库或运行状态文件。
- 远端：公开仓库提交 `3394b33` 的 GitHub Actions Run `30635506117` 成功，Python 3.9、
  Python 3.12、Frontend 和 Containers 四个 job 均通过。
