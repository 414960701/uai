---
kind: acceptance
id: CHG-0031-ACCEPTANCE
status: accepted
---

- [x] Agent 可以保存 draft、发布 draft、查看版本状态和 latest 标签。
- [x] 回滚只移动 latest；回滚后继续保存/发布分配新的 revision 编号。
- [x] 编辑器提供历史版本预览、从历史继续编辑、回滚和冲突提示。
- [x] Run 与 child mount 都能选择 draft/published 版本，留空跟随 latest。
- [x] 旧 Instance/Run 兼容字段和旧数据库读取路径被移除或明确拒绝。
- [x] 前后端门禁全部通过。
