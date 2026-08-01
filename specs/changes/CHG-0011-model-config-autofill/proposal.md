---
kind: change-proposal
id: CHG-0011
status: implemented
target: 0.2
implementation_status: implemented
requirements:
  - CFG-007
---

# ModelConfig 厂商与服务地址联动

统一 `ModelConfig` 和侧边栏入口已经由 CHG-0009 落地。剩余的首用摩擦是：用户选择
服务地址后，模型选择器仍可能保留上一个厂商的模型，必须再手动筛选。

本变更为常用服务地址增加 provider/default model 元数据。选择厂商或已知服务地址时，
控制台同步 provider、端点和推荐模型；输入未知自定义地址时保留用户当前模型，不猜测
协议或凭证。多个 `ModelConfig` 仍然是多个可独立轮换的 AK/模型连接。
