---
kind: design-delta
id: CHG-0031-DESIGN
status: in_progress
target: 0.1
---

# Design decisions

1. `PluginKind.SANDBOX` 与 `SandboxBinding` 只描述能力和配置；`sandbox.py` 是 Docker 边缘
   适配器，核心只依赖 `SandboxProvider`。
2. `SandboxRequest.command` 是 argv 数组，不接受 shell 字符串；Docker 命令由适配器构造，
   模型无法插入 `--privileged`、`--mount`、`--cap-add`、环境变量或 Docker socket。
3. Docker provider 固定 `--network=none`、`--read-only`、`--cap-drop=ALL`、
   `--security-opt=no-new-privileges:true`、`--pull=never`、非 root UID、tmpfs workspace，
   并把资源/输出/超时限制取绑定与调用请求的更严格值。
4. provider 可以选择受控 OCI runtime `runc`、`runsc` 或 `kata-runtime`；Firecracker、Wasm
   和远程 executor 通过新 manifest 实现，而不是给 Docker adapter 添加特殊对象。
5. `tool.sandbox_exec` 显式 opt-in，默认工具集不包含它；推荐 `confirm` 权限，真实审批
   资源仍遵守 Foundation 中的后续 Approval 契约。
6. 当前只保证单进程 adapter 的边界测试；Docker daemon 权限、镜像供应链、DNS/egress、
   kernel escape 和多租户隔离需要部署级 TCK/故障测试，不能写成当前已完成能力。
