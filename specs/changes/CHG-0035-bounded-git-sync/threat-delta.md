---
kind: threat-delta
id: CHG-0035-THREATS
status: in_progress
target: 0.1
---

- 仓库越界：binding 绑定部署侧仓库根目录，模型不能选择 root、remote 或 branch。
- 远端/分支副作用：remote 使用 binding 配置，push 只推当前 checkout branch；工具不提供 force/delete/tag。
- 命令注入：无 shell 字符串和任意 argv；Git 子命令、flags、pathspec 均由适配器生成。
- 凭证泄漏：Token 不在 binding、prompt、事件、日志、结果或命令参数中；askpass 脚本不含 Token，环境和临时脚本在进程结束后清理。
- 结果泄漏：子进程输出先做已知 credential-like 文本脱敏并有界返回；凭证仍不进入 binding、prompt、事件或日志。
- 重复外部副作用：当前 `0.1` 仍是单进程工具调用，不宣称 outbox/idempotency；push 失败保留本地 commit，后续按正常 Git 流程重试。
