---
kind: requirements-delta
id: CHG-0031-REQUIREMENTS
status: proposed
target: 0.1
---

## EXT-009 — 可插拔沙箱端口

WHEN 扩展注册 sandbox provider
THE SYSTEM SHALL 通过 UAI Forge 自有 `SandboxProvider`、`SandboxRequest`、`SandboxResult`
和 `PluginManifest(kind=sandbox)` 合同发现、校验和创建 provider；核心不得暴露 Docker、
gVisor、Kata、Firecracker 或 Wasm 对象。

WHEN `tool.sandbox_exec` 被显式绑定并调用
THE SYSTEM SHALL 只接受有界 argv、stdin、timeout 和 output 参数，把执行委托给已注册的
sandbox provider，并返回有界、结构化、可审计结果；不得拼接 shell 或传入宿主环境变量。

## SEC-008 — 默认硬化与 fail closed

WHEN 使用内置 `sandbox.docker`
THE SYSTEM SHALL 在子容器中使用无网络、只读 rootfs、临时工作区、非 root UID、删除全部
Linux capabilities、`no-new-privileges` 和 CPU/内存/pids/超时/输出限制；镜像必须由绑定
显式指定，并默认不在线拉取。

WHEN sandbox 配置、命令、超时、输出或 provider 不符合边界
THE SYSTEM SHALL 在启动子进程前以稳定的非敏感错误失败；超时/取消必须终止执行并尝试
清理容器，不把 Docker socket、宿主挂载、凭据或原始进程句柄交给 Agent。

## DEP-005 — 沙箱部署边界

WHEN 部署者启用 Docker sandbox
THE SYSTEM SHALL 要求 dedicated/rootless Docker 或受认证保护的远程 sandbox executor；
部署不得把 rootful Docker socket 暴露给不可信 Agent 路径，并必须由部署 profile 负责镜像
allowlist/digest、宿主 egress、runtime profile、kernel 更新和 escape/故障演练。
