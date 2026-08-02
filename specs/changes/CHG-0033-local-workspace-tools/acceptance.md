---
kind: acceptance
id: CHG-0033-ACCEPTANCE
status: pending
---

- [ ] Agent 显式绑定 `tool.workspace` 后可读取项目、查看 Git 差异、应用小范围补丁并运行后端测试。
- [ ] 越界路径、敏感文件、删除/symlink/binary patch、任意命令和超时均有稳定失败证据。
- [ ] 默认新建 Agent 不自动挂载工作区工具。
- [ ] 本地 Compose 以非 root 用户提供 `/workspace`，不挂载 Docker socket。
- [ ] 文档明确该能力不是生产级共享工作区或沙箱隔离。
