---
kind: change-proposal
id: CHG-0034-PROPOSAL
status: accepted
target: 0.1
---

# 工具凭证与部署侧凭证引用

UAI Forge 已能把模型凭证保存在控制面，但 Git、代码托管和其他外部工具仍没有独立的凭证生命周期。把这类 token 放进 Agent 提示词、工具 JSON、事件或日志会破坏密钥只存引用的边界，也无法支持部署侧轮换。

本 change 增加 tenant-scoped `ToolCredential` 资源和控制台“工具凭证”页面。操作者只在提交时输入一次明文；控制面使用 bootstrap 注入的 master key 加密保存，并只向客户端返回掩码和稳定的 credential ID。Agent/工具绑定只保存 `credential_ref`，运行时由受控 resolver 在工具适配器边界短暂解析。

本 change 不新增 Git push 工具，也不授权远程推送；它提供后续 Git/代码托管适配器所需的安全凭证生命周期。远程副作用、固定仓库/分支和部署权限仍须由后续工具契约单独规定。
