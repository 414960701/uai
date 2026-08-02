---
kind: acceptance
id: CHG-0038-ACCEPTANCE
status: pending
---

- [ ] 单个普通工具和委派结果不会超过 Runtime 的上下文结果上限。
- [ ] 历史过大时系统合同和当前任务仍可见，旧 memory/旧工具轮次可压缩，完整工具轮次不被拆开。
- [ ] `context_compacted` 事件包含安全的压缩度量，事件、日志和快照无秘密。
- [ ] Provider cache 命中仍可观测，且不改变总令牌/步骤/工具/超时预算语义。
- [ ] 新研究 Run 复用已有索引和笔记，只补充增量来源，并把结论、取舍、UAI 转译、测试和下一步问题提交到 Git。
- [ ] 后端、前端和 Compose 门禁通过，最新 Agent revision 真实产生研究/代码/测试/Git 闭环证据。
