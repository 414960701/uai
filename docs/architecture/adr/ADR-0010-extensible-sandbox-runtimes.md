---
kind: decision-record
id: ADR-0010
status: accepted
date: 2026-08-02
supersedes: []
---

# 可插拔沙箱运行时

## Context

远程 Agent 的代码执行、文件处理和浏览器辅助任务需要进程隔离，但 Docker、gVisor、Kata、
Firecracker 和 Wasm 的安全/性能边界不同。把任一容器 SDK 或 runtime 对象放进 Agent 核心
会让模型合同、权限和部署耦合到单一实现；把 Docker socket 交给不可信执行路径则等价于
扩大宿主机管理权限。

## Decision

1. 增加自有 `SandboxProvider` 端口、`SandboxRequest`/`SandboxResult` 合同和 `sandbox` plugin kind。
2. 每个 sandbox adapter 通过 manifest 注册；`sandbox.docker` 是首个内置实现，其他 OCI、
   microVM、Wasm 或远程 executor 只能在边缘适配器中接入。
3. Agent 工具只能提交 argv、stdin 和可收紧的 timeout/output 参数；禁止 shell 字符串、
   host mount、Docker socket、模型自定义 environment/capability/profile。
4. Docker adapter 默认使用无网络、只读 rootfs、无 capability、no-new-privileges、非 root、
   tmpfs 工作区和 cgroup 资源限制；镜像由部署侧预置，调用时 `--pull=never`。
5. 沙箱执行工具是显式 opt-in 且建议 `confirm`；新建 Agent 的安全默认工具不自动挂载。
6. 根 Run 的预算、取消、超时和审计仍由 UAI Forge 核心负责；adapter 不得生成脱离父 Run 的
   长期任务或将 Secret 自动复制进沙箱。

## Consequences

- Docker/runc 是容易落地的基线，runsc/Kata 可以在不改变 Agent 合同的情况下增强隔离；
  Firecracker/Wasm 需要各自的 worker/能力模型。
- 需要部署侧维护 rootless/dedicated Docker、镜像签名/allowlist、egress policy、kernel 和
  runtime patch；本地 adapter 不单独提供完整 sandbox 安全保证。
- 沙箱 API 和 registry 可以先在单进程运行，未来再由 checkpoint/lease/remote executor
  承载，不阻塞当前 0.1.x 的协议优先架构。
