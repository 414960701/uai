---
kind: threat-delta
id: CHG-0004-THREAT
status: accepted
---

# Threat delta

| 威胁 | 处置 |
|---|---|
| 后台保存与 manifest 不兼容的配置 | 持久化前统一 registry gate，返回结构化 422 |
| 旧数据或替代 Repository 绕过保存校验 | Run 提交与每个执行 frame 二次验证 |
| provider 伪造工具参数 | middleware 前按实际 ToolPlugin Schema fail closed |
| middleware 注入额外 authority 参数 | invoke 前再次验证 |
| 错误响应泄露参数或 Secret | 丢弃 jsonschema message/value，只保留 path/keyword |
| 停用记忆仍读取或保存会话 | disabled binding 不实例化 adapter |

仍接受的风险：管理员预安装的 in-process Python 插件与宿主进程等权；远程 `$ref`、
插件隔离、签名和供应链验证属于后续插件信任工作。
