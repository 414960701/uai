---
kind: design-delta
id: CHG-0001-DESIGN
status: accepted
target: 0.1.x
---

# Design delta

## 合同

```text
InstanceConfigOverrides (extra=forbid)
└── policy?: InstanceExecutionPolicyOverrides (extra=forbid)
    ├── max_steps?
    ├── max_depth?
    ├── max_tool_calls?
    ├── max_parallel_children?
    ├── timeout_seconds?
    ├── token_budget?
    └── fail_fast?
```

字段约束复用 `ExecutionPolicy` 的边界。所有输入先经过递归明文 credential 检查，再由
上述合同拒绝未知字段。

## 合并

1. 按 Instance 固定 revision（或提交时解析出的 latest）读取基础 `AgentSpec`。
2. 从基础 spec 的 Python dump 构造独立候选值。
3. 数值字段使用 `min(base, override)`；`fail_fast` 使用逻辑 OR。
4. 用 `AgentSpec.model_validate` 完整校验候选值。
5. 只把 effective spec 交给本次 Run；不调用 revision 保存接口。

这不是通用递归 merge。没有声明的叶子节点不可覆盖。

## 上下文

RunManager 在初始 metrics 中记录 `instance_id`、`environment` 和无 Secret 的
`effective_policy`。Runtime 从服务端生成的 Run 读取这些值并加入 provider metadata 与
middleware/tool context；不信任客户端 `request_metadata` 提供同名能力。

`environment` 在 `0.1.x` 只是适配器可见的非敏感部署标识，不代表已实现云调度或正式
deployment profile。
