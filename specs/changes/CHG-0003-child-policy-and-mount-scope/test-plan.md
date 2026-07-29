---
kind: test-plan
id: CHG-0003-TEST-PLAN
status: accepted
---

# Test plan

- 宽 root policy 下，child 的本地 step、tool、token 上限分别先触发。
- 慢 child 在自己的 timeout 内失败，Run 不等待 root timeout。
- root 并发较宽时，中间 child 的本地 fan-out 峰值不超过其上限。
- 既有三层、根并发为 1 的委派仍无死锁。
- 缺失/`null` allowlist 保持旧 mount 行为；显式空列表拒绝全部插件工具。
- 显式 allowlist 允许列出的插件、隐藏并拒绝未列出插件。
- 上游只允许 echo 时，下游即使列出 calculator 也不能恢复 calculator。
- mount allowlist 不能覆盖 child ToolBinding 的 `deny` / `confirm`。
- 恶意 provider 伪造被隐藏 tool call 时，没有 middleware/tool started/tool invoke。
- 全量运行 `python -m pytest backend/tests -q`。
