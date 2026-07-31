---
kind: design-delta
id: CHG-0006-DESIGN
status: accepted
target: 0.1.x
---

# Design delta

`.openai/hosting.json` 继续作为 Sites 工具在本机识别既有项目的事实源，但不再进入 Git
或 Docker build context。`.openai/hosting.example.json` 只声明 `d1`、`r2` 的中性空值，
不包含可被 Fork 误用的 `project_id`。

`vite.config.ts` 在 Node 配置阶段读取可选 hosting 文件：文件不存在时返回
`{ d1: null, r2: null }`；文件存在但 JSON 损坏时保持 fail closed 并让构建失败。这样
普通 checkout、本地发布门禁和容器构建不需要临时生成部署文件，而本地 Sites 部署仍能读取真实
binding 名称。

仓库卫生测试验证 ignore 规则、示例内容和可选加载约定。发布审计同时扫描当前索引与所有
现有提交中的维护者账号标识、本机绝对路径和常见凭据签名；非 Secret 的历史项目 ID 记录
为已知历史，不做破坏性重写。
