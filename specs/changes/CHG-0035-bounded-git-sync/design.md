---
kind: design-delta
id: CHG-0035-DESIGN
status: in_progress
target: 0.1
---

# Design

1. `tool.git` 作为普通 UAI Forge `ToolPlugin` 注册，不把 GitPython、GitHub SDK 或任何供应商
   对象泄漏到核心合同；binding 只配置仓库根目录、凭证引用和可选 remote 名称。
2. `GitTool._scope` 解析绑定仓库、配置的 remote 和当前 checkout branch；不要求固定远端 URL、
   分支集合或路径 allowlist，模型也不能从参数覆盖这些绑定配置。
3. `status`、`diff`、`pull`、`push` 使用适配器生成的固定 argv；pull 执行普通 `git pull --no-tags`，
   push 推送当前 checkout branch，不提供 force、远端删除、tag 或模型可控 flags。
4. `commit` 使用普通 `git add --all` 后提交全部当前工作区变更；`commit_and_push` 复用 commit
   再推送当前 branch，不增加推送前审计或人工确认门槛。唯一的提交前拦截是检测到 credential-like
   内容时拒绝提交并清理暂存区，以满足密钥不落盘合同。提交通过固定 `core.hooksPath=/dev/null`
   禁止仓库 hook 在 Agent 进程内执行。
5. `AgentRuntime` 只把带下划线的私有 `ToolCredentialPort` 对象放入工具 invoke context；该对象
   不进入 ModelMessage、RunEvent、preview、metrics 或持久化 JSON。GitTool 只在外部同步动作调用
   `resolve_tool_credential_secret(tenant_id, credential_ref)`。
6. HTTPS 认证使用临时、无密钥内容的 askpass 脚本和短暂 `UAI_GIT_TOKEN` 环境变量；结果先做已知
   secret 和 credential-like 文本脱敏，再返回 action、branch、remote name、SHA、状态和有界输出。
7. `tool.git` 不加入 `default_tool_bindings`；控制台提供显式添加与常规仓库 JSON 模板，凭证页面
   仍只显示 ID 和掩码。
