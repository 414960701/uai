---
kind: design-delta
id: CHG-0030-DESIGN
status: in_progress
target: 0.1
---

# Design decisions

1. `web_tools.py` 实现 UAI Forge 自有 `ToolPlugin` 边界；只在插件适配器边缘使用
   `httpx`，不把搜索引擎、浏览器或供应商对象放进核心 Agent/Run 合同。
2. 默认搜索适配器使用 HTTPS Bing RSS 结构化结果，并保留 `endpoint` 配置作为可替换的
   搜索服务边界；`web_json` 和 `web_rss` 分别提供不带凭据的公开结构化接口与订阅读取。
   生产部署应按上游服务条款和网络出口策略选择合规端点。
3. Web Fetch 使用标准库 HTML parser 做正文提取，只保留 title/text/links 等有界结构化
   结果；页面内容带 `untrusted=true` 和明确提示，不被当作 Agent 指令。
4. URL 校验拒绝非 HTTPS、公网以外地址、userinfo、fragment 和常见敏感 query key；手动
   处理最多三次重定向，并在每一跳重新校验。DNS rebinding/出口 ACL 仍属于部署边界，
   不虚假宣称本地代码单独提供完整 SSRF 防护。
5. API 通过 `model_fields_set` 区分“未提供 tools”和显式空列表；老 Agent 数据不被读取
   时自动改写。新建前端表单和后端 API 同时给出默认值，编辑已有 Agent 保留其历史绑定。
6. 默认工具均为只读；浏览器自动化、文件系统、代码执行、外部业务系统和长期记忆留在
   后续带审批、沙箱或 workspace/身份合同的变更中。公开 JSON/RSS 仍只属于 HTTP 读取，
   不等同于私有 API、数据库、邮箱或业务连接器。
7. Runtime 对每次 Tool 调用施加默认 30 秒边界；绑定或调用参数可以进一步收紧，
   但不得超过 Agent 的 Run 超时。fail-fast 取消并行工具时使用有界排空，避免不响应的
   扩展把 Run 永久留在运行中；超时以稳定的非敏感运行错误记录。
