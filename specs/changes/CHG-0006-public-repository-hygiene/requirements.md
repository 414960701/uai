---
kind: requirements-delta
id: CHG-0006-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### SEC-007A — 账号绑定部署元数据不得进入公开源码

WHEN UAI Forge 源码发布到公开仓库
THE SYSTEM SHALL 不跟踪个人或环境专属的 Sites `project_id`、真实 Secret、本机绝对路径、
运行数据库或构建状态；真实 `.openai/hosting.json` SHALL 保持本地并被 Git 与 Docker
build context 忽略。

### SEC-007B — 无个人部署文件的可移植构建

WHEN 开发者从干净 checkout 安装、检查或构建 Web 控制后台
THE SYSTEM SHALL 在 `.openai/hosting.json` 不存在时使用无 D1/R2 binding 的中性默认值，
并提供不含 `project_id` 的版本化示例；lint、typecheck、production build/test 不得依赖
维护者个人的部署配置。
