---
kind: acceptance
id: CHG-0031-ACCEPTANCE
status: pending
---

- [x] 核心通过自有 sandbox provider 端口支持扩展，Docker/gVisor/Kata/Firecracker/Wasm 不泄漏为核心对象。
- [x] `sandbox.docker` 和 `tool.sandbox_exec` 已注册，默认 Agent 不自动挂载。
- [x] Docker argv builder 固定无网络、只读 rootfs、无 capability、no-new-privileges、非 root、资源限制和 `--pull=never`。
- [x] 2026-08-02 当前 Docker 29.5.2 daemon smoke：`alpine:3.20` 非 shell argv 执行成功；1 秒 timeout 返回 `timed_out=true`；结束后无 `uai-sbx-*` 孤儿容器。
- [ ] 在 rootless/dedicated Docker 上完成真实执行、超时、取消和孤儿容器清理 smoke。
- [ ] 完成镜像供应链、egress、runtime profile、kernel/escape 和租户配额故障演练。
