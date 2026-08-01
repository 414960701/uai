---
kind: task-delta
id: CHG-0031-TASKS
status: in_progress
---

- [x] 增加 `SandboxProvider`、请求/结果合同、sandbox plugin registry 和公开扩展面。
- [x] 增加 `sandbox.docker` 的 argv builder、rootfs/network/capability/resource hardening。
- [x] 增加显式 opt-in 的 `tool.sandbox_exec`，默认 Agent 不自动挂载。
- [x] 记录 Docker、gVisor、Kata、Firecracker、Wasm 与远程 executor 的研究与部署边界。
- [ ] 增加真实 Docker/rootless/runsc/Kata profile smoke 与 timeout/cancel/cleanup 故障矩阵。
- [ ] 增加生产镜像签名/allowlist、dedicated executor、egress policy 和租户级配额合同。
