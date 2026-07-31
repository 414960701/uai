---
kind: requirements-delta
id: CHG-0008-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### EXT-007 — 生产 Provider 边界

WHEN UAI Forge 以产品运行时启动
THE SYSTEM SHALL 只在 registry 中暴露真实可调用的 provider 适配器；测试 provider、示例
拓扑和伪造模型只能位于 `backend/tests` 测试边界，不得进入产品包、控制 API 或默认数据库。

### DEP-004 — 可移植发布门禁

WHEN 开发者从公开 checkout 构建或验收 UAI Forge
THE SYSTEM SHALL 不要求仓库内托管平台 workflow；发布验证由版本化 Makefile、测试命令和
容器 smoke 脚本显式运行，且删除 workflow 不影响应用构建或运行。
