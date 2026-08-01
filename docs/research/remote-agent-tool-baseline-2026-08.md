---
kind: research-note
id: REMOTE-AGENT-TOOL-BASELINE-2026-08
date: 2026-08-02
status: used_for_chg_0030
---

# 远程 Agent 基础工具盘点

本次按“远程 Agent 常用、可复用、能默认安全开启”筛选资料，重点看公开协议和工具目录，
而不是把某一家供应商的 SDK 类型带进 UAI Forge 核心。检索时间为 2026-08-02。

## 看到的共同能力

| 能力 | 常见工具 | 默认策略 |
|---|---|---|
| Web 检索 | `search` / `web_search`，返回标题、URL、摘要和引用 | 只读、有界、外部内容标为不可信 |
| 页面访问 | `fetch` / `web_fetch`，把公开页面转成文本 | 只读，HTTPS 公网地址，重定向和响应大小复核 |
| 公开结构化 Web | `web_json`、`web_rss` / `web_atom`，读取公开 API 和订阅 | 只读、有界、不接受凭据或自定义请求头 |
| 时间与计算 | `time`、`calculator` | 低风险，可默认挂载 |
| 私有知识 | `file_search`、向量库/数据库检索 | 需要 workspace/tenant/ACL，不默认开放 |
| 浏览器/计算机 | 浏览器导航、截图、点击、输入、下载 | 能产生副作用，需要沙箱、审批和人工接管，不默认开放 |
| 文件与代码 | 文件系统、Git、shell、代码执行、数据分析 | 需要 workspace 权限和资源配额，不默认开放 |
| 协作与业务系统 | 子 Agent、GitHub、邮件、日历、工单、数据库 | 需要身份、scope、审计和幂等合同，不默认开放 |
| 记忆与任务 | memory、todo、sequential thinking | 任务可视化可默认；跨会话 memory 需要 retention/tenant 规则 |

## 资料来源

- [OpenAI Web search tool](https://platform.openai.com/docs/guides/tools-web-search)：公开 Web
  检索通常以搜索工具和引用结果作为模型外部知识入口。
- [OpenAI Computer use](https://platform.openai.com/docs/guides/tools-computer-use)：浏览器/桌面
  控制属于高风险交互工具，需要确认和隔离，不能与只读 HTTP 抓取混为一谈。
- [OpenAI File search](https://platform.openai.com/docs/guides/tools-file-search)：私有文件检索
  依赖文件集合、权限和索引边界，不能因为有 Web 工具就默认获得 workspace 访问。
- [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture) 与
  [MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts)：把外部工具、
  资源和提示作为协议边界，支持不同服务接入但不要求宿主核心暴露服务端类型。
- [MCP reference servers](https://github.com/modelcontextprotocol/servers/tree/main/src)：参考目录
  中可见 `fetch`、`filesystem`、`git`、`memory`、`sequentialthinking`、`time` 等基础能力，
  也说明文件/Git/记忆不应和无权限的公共 Web 读取使用同一默认范围。
- [Bing RSS search endpoint](https://www.bing.com/search?format=rss)：本变更的默认无密钥示例
  搜索端点，工具层保留可替换 `endpoint` 配置；部署者需要自行核对上游服务条款、出口策略
  和商业使用限制，不把此端点宣称成生产搜索 SLA。

## 这次落地的范围

CHG-0030 落地 `tool.web_search`、`tool.web_fetch`、`tool.web_json`、`tool.web_rss`、
`tool.calculator` 和 `tool.utc_now` 六个默认基础工具。Web 工具不执行脚本，不提交表单，
不访问私网，不接受凭据，不下载任意二进制，且输出明确带 `untrusted` 提示。浏览器自动化、文件搜索、代码执行、业务连接和持久记忆会在
具有 workspace/identity/approval/sandbox 合同后再单独变更。
