---
kind: acceptance
id: CHG-0029-ACCEPTANCE
status: accepted
---

- [x] Run 目标统一为 Agent，latest/显式 revision 均有后端回归证据。
- [x] latest 作为可回滚指针移动，继续发布不复用历史 revision；child mount 留空跟随 latest。
- [x] Instance API、运行时上下文和管理 Tab 已移除；旧数据未被破坏性删除。
- [x] 前端 RunModal 提供 revision 选择并默认 latest。
- [x] 前后端门禁全部通过。
