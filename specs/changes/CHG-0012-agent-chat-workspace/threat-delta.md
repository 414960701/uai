---
kind: threat-delta
id: CHG-0012-THREAT
status: implemented
---

# Threat delta

| 威胁 | 设计处置 | 剩余边界 |
|---|---|---|
| 误把客户端会话列表当成持久聊天数据 | 仅聚合现有 Run，文案和规范明确 0.1.x 无 Session store | 后续需要正式 Session/Message 合同时另行变更 |
| API Key 进入 URL 或对话历史 | Key 只在内存 headers 中使用；session/resource 只包含非敏感 ID | 可信身份/tenant 仍是当前 0.1.x 限制 |
| SSE 重放重复助手结果 | 使用已有 sequence reducer；Run 终态只由服务器事件/查询确认 | 运行进程重启恢复仍未实现 |
| 工具中文展示导致排障丢失稳定标识 | 中文名旁保留 code 标签和可读事件 type | 第三方 manifest 需要提供更完整本地化文案时再扩展协议 |
| 失败重试覆盖原始证据 | 重试创建新 Run，旧 Run 和事件只读保留 | 0.1.x 没有跨进程审计索引 |
