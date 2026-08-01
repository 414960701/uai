---
kind: change-proposal
id: CHG-0031
status: in_progress
target: 0.1
date: 2026-08-02
implementation_status: in_progress
requirements:
  - EXT-009
  - SEC-008
  - DEP-005
---

# 可插拔子容器与沙箱运行时

远程 Agent 常用的代码执行、文件转换和数据处理不能直接运行在控制面进程。为保持扩展性，
本变更增加 UAI Forge 自有的 `SandboxProvider` 端口和 manifest 注册点，首个内置适配器
使用子 Docker 容器；同一端口预留 gVisor、Kata、Firecracker、Wasm 和远程 executor。

沙箱不是新建 Agent 的默认能力。`tool.sandbox_exec` 只有在用户显式配置 sandbox provider、
镜像和权限后才会出现在执行上下文；默认只读 Web 工具仍保持最小权限语义。

研究依据见 `docs/research/sandbox-runtime-baseline-2026-08.md`，部署/隔离承诺不得超出
Docker、runtime、kernel、镜像和 egress 的实际故障测试证据。
