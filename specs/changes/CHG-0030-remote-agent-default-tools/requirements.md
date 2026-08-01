---
kind: requirements-delta
id: CHG-0030-REQUIREMENTS
status: proposed
target: 0.1
---

## EXT-008 — 受限远程只读工具

WHEN Agent 调用内置 `tool.web_search`
THE SYSTEM SHALL 使用有界 query/max-results 参数，通过可配置的 HTTPS 搜索端点返回
标题、公开链接和摘要，并把结果标记为外部不可信参考资料；工具不得把请求中的凭据写入
配置、事件、日志或返回值。

WHEN Agent 调用内置 `tool.web_fetch`
THE SYSTEM SHALL 只访问公开 HTTPS URL，在每个重定向跳转重新执行公网地址校验，并限制
超时、响应字节数和输出字符数；工具不得执行 JavaScript、提交表单或返回原始 HTML。

WHEN Agent 调用内置 `tool.web_json` 或 `tool.web_rss`
THE SYSTEM SHALL 只读取公开 HTTPS JSON、RSS 或 Atom 端点，限制超时、响应字节数和返回
条目/结构化输出大小；结果必须标记为外部不可信参考资料，且工具不得接受自定义凭据或请求头。

WHEN Web 工具遇到私网/本机地址、userinfo、敏感 query 参数、非 HTTPS 协议、超限响应或
上游错误
THE SYSTEM SHALL 以稳定的非敏感错误失败，不发起越界请求，也不回显 URL 中的敏感值。

## UI-007 — 新建 Agent 默认基础能力

WHEN 新建 Agent 请求未显式提供 `tools`
THE SYSTEM SHALL 默认挂载 `tool.web_search`、`tool.web_fetch`、`tool.web_json`、
`tool.web_rss`、`tool.calculator` 和 `tool.utc_now`，每项使用稳定 alias 与 `auto` 权限。

WHEN 用户显式提供 `tools: []`
THE SYSTEM SHALL 保留空工具配置，不隐式恢复默认挂载。

WHEN 用户打开新建 Agent 表单
THE SYSTEM SHALL 将上述可用内置工具显示为已选状态，并允许逐项取消或收紧权限。

## CFG-008 — 可直接使用的默认预算

WHEN 新建 Agent 未覆盖执行策略
THE SYSTEM SHALL 使用 `max_steps=20`、`max_depth=6`、`max_tool_calls=64`、
`max_parallel_children=6`、`timeout_seconds=300` 和 `token_budget=64000`；新建子 Agent
挂载的默认 `max_concurrency` SHALL 为 4。前后端默认值必须一致。
