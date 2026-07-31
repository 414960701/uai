---
kind: design
id: CHG-0009-DESIGN
status: accepted
---

## 领域合同

`ModelConfig` 是唯一可持久化模型连接合同：`provider` 是注册表适配器 ID，`protocol`
由 manifest 派生，`model`/`base_url`/`config` 是非敏感连接参数，`masked_secret` 是
响应元数据。写入合同只在 POST/PATCH 接受一次性 `secret`，仓储只保存密文。

`ModelBinding` 只含 `model_config_id` 和非敏感扩展覆盖。运行时读取租户配置，创建带有
private resolved provider/model/secret 的短生命周期 binding；private 字段不参与 Pydantic
序列化。

## Provider manifest

Manifest 增加 `api_protocol`、`credential_required` 和 `model_catalog`。模型目录是内置
适配器的公开元数据，不是租户配置，也不是运行时发现的任意模型列表；每项包含模型 ID、
显示名、用途提示、推荐级别和官方来源链接。

## 协议适配器

OpenAI adapter 保持 Chat Completions 请求。Claude adapter 将核心 `ModelMessage` 映射
为 Messages API 的 system、user、assistant、tool_result/tool_use blocks，并把 Anthropic
响应还原为核心 `ModelOutput`，只暴露最小 usage/id/finish 元数据。

## 数据库

新鲜 SQLite 只创建 `model_configs`；旧的 credential/model profile API 和建表代码删除。
不做旧表数据迁移。ModelConfig 删除前扫描所有 Agent revisions，引用存在时返回 409。

## UI

侧边栏新增“凭证&模型配置”页面。页面按“连接配置 / 新建配置 / 已保存配置”组织，协议、
provider、模型使用选择项，复杂 provider 参数保留高级 JSON；Agent 新建/修订只显示启用
的 ModelConfig 下拉框。
