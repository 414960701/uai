---
kind: research-note
id: SANDBOX-RUNTIME-BASELINE-2026-08
date: 2026-08-02
status: used_for_chg_0031
---

# 远程 Agent 沙箱运行时盘点

本次优先核对官方文档和上游项目设计，重点是“Agent 能提交一个受限进程执行请求”与“宿主
执行器如何隔离”之间的边界。结论不是把 Docker、gVisor 或 Firecracker 的对象引入核心，
而是为它们定义统一的 UAI Forge `SandboxProvider` 端口。

## 一手资料与结论

| 资料 | 关键事实 | 对 UAI Forge 的约束 |
|---|---|---|
| [Docker Engine security](https://docs.docker.com/engine/security/) | Docker 使用 namespaces 与 cgroups；daemon、宿主挂载和 capability 是重要攻击面 | 子容器不能拿宿主目录、Docker socket、特权或额外 capability；资源限制属于 DoS 防护的必要层 |
| [Docker Rootless mode](https://docs.docker.com/engine/security/rootless/) | daemon 和容器可以作为非 root 用户运行 | 部署优先 rootless/dedicated daemon；控制面不能把 rootful socket 暴露给不可信 Agent |
| [Docker seccomp](https://docs.docker.com/engine/security/seccomp/) | Docker 支持 seccomp profile 来限制系统调用 | 保留 runtime 默认 seccomp，并允许部署侧替换更严格 profile；核心不接受模型提供的 profile |
| [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) | memory/CPU/pids 等 cgroup 限制可以约束单个容器 | 每次执行必须有父 Run 的 timeout、输出、CPU、内存、pids 上限，不能让模型自行放大 |
| [gVisor](https://gvisor.dev/docs/) | `runsc` 提供用户态应用内核并可接入容器工具链 | 作为 Docker/OCI runtime 选项；兼容性和性能由适配器/部署 profile 验证 |
| [Kata Containers](https://katacontainers.io/) | 通过轻量 VM 提供更强的容器隔离，并接入容器生态 | 作为 `kata-runtime`/OCI runtime 或独立 provider；需要 Linux/KVM 与容量验收 |
| [Firecracker design](https://github.com/firecracker-microvm/firecracker/blob/main/docs/design.md) | microVM 以 KVM、seccomp、namespace、cgroup 和 jailer 形成分层隔离 | 不伪装成 Docker runtime；用独立 worker/provider 适配 `SandboxProvider`，并由宿主过滤 egress |
| [OCI runtime-spec](https://github.com/opencontainers/runtime-spec) | OCI 定义容器运行时配置与生命周期边界 | Docker、runsc、Kata 等留在边缘；核心只看稳定的 request/result/manifest |
| [Wasmtime](https://docs.wasmtime.dev/) | Wasm 是另一种受限执行模型，不等价于 Linux 容器 | 未来可提供 `sandbox.wasm`，但必须单独定义模块、能力和 I/O 合同 |
| [Alibaba OpenSandbox](https://github.com/alibaba/OpenSandbox) | 社区项目把多种 sandbox backend 与 Agent 场景组合 | 可作为外部 executor 参考，不把其 API/SDK 类型写入 UAI Forge 核心 |

## 推荐分层

```text
Agent tool call (argv + stdin, no shell)
        ↓
UAI Forge SandboxProvider (request/result, timeout/cancel/output budget)
        ↓
Docker adapter → runc / runsc / kata-runtime
VM adapter    → Firecracker / other microVM worker
Wasm adapter  → Wasmtime / other Wasm runtime
Remote adapter→ dedicated sandbox service over authenticated API
```

第一阶段实现 `sandbox.docker`：子容器使用 `--network=none`、只读 rootfs、临时 tmpfs、
`--cap-drop=ALL`、`no-new-privileges`、非 root UID、pids/CPU/内存/输出/超时边界，并以
argv 调用 Docker CLI，不拼接 shell。镜像由运维预置且使用 `--pull=never`；模型不能传入
Docker flags、挂载、环境变量、socket、runtime profile 或凭据。

`sandbox.docker` 的 `runtime` 只允许受控的 `runc`、`runsc`、`kata-runtime` 值。Firecracker、
Wasm 和远程执行器通过新的 manifest/adapter 接入，不改变核心 Agent/Run 合同。

## 明确不做的安全承诺

- Docker 容器不是 VM；共享 Linux kernel 的风险仍由部署者承担。
- 控制面进程不能直接把 `/var/run/docker.sock` 挂到含不可信工具的容器；需要 rootless、
  dedicated executor 或受认证保护的远程 Docker API。
- DNS、宿主 egress、防止恶意镜像和 kernel escape 不能由本地 argv builder 单独证明；必须
  有镜像 allowlist/digest、网络策略、runtime profile、宿主补丁和故障演练。
- 当前实现是单进程、显式 opt-in adapter，不等于生产级多租户 sandbox service。
