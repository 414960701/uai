---
kind: acceptance
id: CHG-0006-ACCEPTANCE
status: passed
---

# Acceptance

- [x] 当前待发布树不再包含维护者个人 Sites `project_id`。
- [x] 本地真实 hosting 文件仍保留且被 Git/Docker 忽略。
- [x] 干净 checkout 无 hosting 文件时前端门禁通过。
- [x] 本地 lint、typecheck、build/test 与容器门禁不依赖仓库内自动化 workflow。
- [x] 当前树除已处理 hosting 文件外无账号、本机路径或凭据签名发现。
- [x] 变更推送前已完成本地发布门禁验证。

## 本地验收证据（2026-07-31）

- 前端：无真实 hosting 文件的 lint、typecheck、production build 与 4 项 Node 测试通过。
- 后端：`65 passed in 3.78s`，compileall 与 pip check 通过。
- 依赖与配置：production audit 为 0 vulnerabilities；Compose、Shell/Node 语法和
  `git diff --check` 通过。
- 容器：双容器 healthy，doctor 正常且 provider 只包含 `openai_compatible`，新数据库为空，
  所有测试容器、network、volume 和临时镜像均已清理。
- 扫描：当前索引只保留中性 hosting 示例；历史命中仅为已公开的非 Secret Sites ID，
  未发现真实凭据、私钥、本机绝对路径、数据库或运行状态文件。
- 远端历史验证：公开仓库提交 `3394b33` 曾完成 Python 3.9、Python 3.12、Frontend 和
  Containers 检查；本次变更不再维护仓库内 workflow。
