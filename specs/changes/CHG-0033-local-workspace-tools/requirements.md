---
kind: requirements-delta
id: CHG-0033-REQUIREMENTS
status: in_progress
target: 0.1
---

## WORKSPACE-001 — 受限本地工作区工具

WHEN Agent 显式绑定 `tool.workspace`
THE SYSTEM SHALL 要求配置绝对 `root_path`，并将所有路径解析限制在该目录及其真实路径以内；绝对路径、路径穿越、越界 symlink 和敏感运行时文件必须 fail closed。

WHEN Agent 调用 `tool.workspace`
THE SYSTEM SHALL 只接受 `list`、有界分段 `read`、`git_status`、有界 `git_diff`、固定的后端测试套件和受校验的 unified patch 操作；不得接受任意 Shell 字符串、环境变量、Docker 参数或网络凭据。

WHEN Agent 使用 `patch`
THE SYSTEM SHALL 只有在 binding 的 `allow_write=true` 时修改工作区；补丁目标必须位于工作区内，禁止二进制、symlink、文件模式和删除操作，并在应用前执行校验。

WHEN Agent 使用测试或 Git 操作
THE SYSTEM SHALL 使用无凭据、最小环境、固定命令、父 Run 的 timeout/取消和有界 stdout/stderr；结果必须是结构化、可审计且不包含原始 patch 或敏感文件内容。

WHEN Agent 提交的 unified patch 未通过校验
THE SYSTEM SHALL 返回不包含 patch 内容的结构化拒绝结果，并保持工作区不变，使 Agent 能停止或在有限预算内纠正补丁；该拒绝不得仅因格式错误升级为父 Run 的不可恢复失败。

WHEN Agent 未显式绑定 `tool.workspace`
THE SYSTEM SHALL 不显示、不创建也不执行该能力；新建 Agent 的默认工具集合保持不变。

## WORKSPACE-002 — 本地部署边界

WHEN 本地 Compose 启用工作区工具
THE SYSTEM SHALL 只把项目目录挂载到容器内 `/workspace`，并以非 root API 用户运行；生产/远程部署不得因该开发配置获得宿主工作区或 Docker socket。

本 change 只提供本地单进程开发能力，不声称实现 MAG-005 的通用 workspace sharing、RBAC、copy-on-write、租户隔离或生产级执行器。
