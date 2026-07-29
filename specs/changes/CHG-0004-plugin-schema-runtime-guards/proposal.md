---
kind: change-proposal
id: CHG-0004
status: implemented
target: 0.1.x
---

# Plugin Schema 与运行时参数防线

## 问题

插件 manifest 已声明 `config_schema`，但若保存和执行边界不消费该合同，后台会接受不可运行
的修订，恶意或异常 provider 也可绕过公开的工具参数 Schema。记忆的启用状态和每 binding
配置同样必须真实影响运行，而不能只是界面字段。

## 范围

- 编译并缓存 provider/tool/memory/middleware manifest 的配置 Schema。
- 在 API、Repository、Run 提交和每个 runtime frame 分层校验 binding。
- 在 middleware 前后校验 tool/delegation arguments。
- 让 disabled memory 与每 binding retention 配置真实生效。
- 使用稳定、无配置值回显的错误合同。

## 非目标

- 不实现插件进程/容器沙箱、签名、SBOM 或导入前 package manifest preflight。
- 不把第三方 Python entry point 视为不可信代码。
- 不实现 Secret manager、完整 PolicyEngine 或通用 credential resolution。
