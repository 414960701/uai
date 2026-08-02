---
kind: design-delta
id: CHG-0033-DESIGN
status: in_progress
target: 0.1
---

# Design

1. `tool.workspace` 作为普通 UAI Forge `ToolPlugin` 注册，不增加第三方框架对象或核心领域依赖。
2. binding 配置包含 `root_path`、`allow_write`、`timeout_seconds`、`max_output_bytes` 和 `max_patch_bytes`；根目录由部署配置显式提供，工具不从模型输入推导宿主路径。
3. `list/read` 使用 `Path.resolve()` 后的 path guard；隐藏凭据、数据库、`.git` 内部、`.ssh` 目录和私钥文件不允许读取或列出。读取按行 offset/limit 截断。
4. `git_status`、`git_diff` 和 `test` 只通过固定 argv 调用，使用无网络/无凭据环境，不接受模型提供的命令名或 flags。当前 test suite 固定为 `python -m pytest backend/tests -q`。
5. `patch` 先检查 unified diff 的所有目标，再调用 `git apply --check` 和 `git apply`；不允许删除、二进制、symlink 或 mode patch。执行使用有界 stdin/stdout/stderr、超时终止和取消清理。
   校验拒绝以不含 patch 内容的结构化 `ok=false` 结果返回给 Agent，允许模型停止或纠正一次补丁；不会因为模型生成的无效补丁直接终止父 Run。
   运行级回归测试验证该拒绝会继续成为可完成的父 Run 结果，而不是 `tool.failed` 终态。
6. 工具调用未显式配置超时时使用 Runtime 的 30 秒默认值；binding 的 `timeout_seconds` 可为固定测试等慢操作提供更宽的上限，单次参数只能进一步收紧，且始终受 Agent Run timeout 约束。
7. Compose 的 `/workspace` bind mount 与构建期 git/pytest 依赖只服务本地开发；`tool.workspace` 不进入六项默认工具，Agent revision 必须显式绑定并允许写入。
