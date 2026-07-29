---
kind: threat-delta
id: CHG-0005-THREAT
status: accepted
---

# Threat delta

| 威胁 | 处置 |
|---|---|
| smoke 覆盖开发者已有容器或 SQLite volume | 每次使用唯一 project/volume；注册 cleanup 前拒绝任何同名 project/network/volume |
| smoke 重标记开发栈共用的本地镜像 | 为前后端生成唯一 image tag，拒绝碰撞并在结束时删除 |
| 动态空闲端口在容器绑定前被其他进程占用 | 端口可显式覆盖；Compose 启动失败时保留明确诊断并只清理测试 project |
| 空控制密钥的 smoke API 短时暴露到局域网 | smoke 强制将 Compose host ports 绑定到 `127.0.0.1` |
| 只检查 demo 页面却宣称 Runtime 可用 | 必须通过 API 发起真实 child delegation 并读取事件 |
| 运行日志或请求写入 Secret | 使用 deterministic mock provider、空控制密钥和非敏感输入 |
| 单节点证据被外推为分布式恢复 | UI、规范和验收明确保留 DEP-003 的 Planned 状态 |
| 公开仓库或运行镜像携带生产 high advisory | 锁定兼容修复版本，裁剪 Web 运行镜像，production-only audit 与 build/test 双重门禁；完整开发链 audit 另行审查记录 |
| 自动 audit fix 引入破坏性主版本 | 禁止无审查 `--force`；保持 vinext/TypeScript/ESLint 主版本 |

仍接受的风险：本 smoke 不验证公网 TLS、可信身份、恶意插件隔离、worker kill、重复投递、
备份恢复或多架构镜像。
