---
kind: adr
id: ADR-0004
status: accepted
date: 2026-07-30
---

# ADR-0004：插件 manifest、信任级与失败模式

## 背景

Python entry point 在加载时执行与宿主等权的代码。仅有 capability 名称和协议主版本，
不足以安全支持后台在线安装、状态迁移或安全 hook。

## 决定

- 插件包在导入实现前提供可读取的版本化 package manifest。
- manifest 声明 core 范围、协议、实现、配置/状态 schema、权限、信任级和迁移。
- 信任级至少区分 core、trusted in-process、isolated process 和 remote。
- 安全、身份、tenant、权限、审批 hook fail closed；观测 hook 才可 fail open。
- 插件状态按 plugin ID 和 state schema version 命名空间保存。
- 控制后台不直接执行任意 `pip install`。

当前 `PluginManifest` 与 entry-point discovery 是 `Partial`；完整 package manifest 和
导入前验证属于后续实现。

## 结果

- 兼容和权限可以在运行代码前审查。
- 未知插件必须隔离或由管理员信任。
- 需要插件 TCK、签名/SBOM、迁移事务和诊断 API。
