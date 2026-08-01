---
kind: test-plan
id: CHG-0020-TEST-PLAN
status: executed
---

- 前端源断言：普通 Enter 换行、`⌘/Ctrl + Enter` 提交、IME composing 防误提交、自动跟随
  ref、暂停跟随和“回到底部”按钮存在。
- 交互回归：普通 Enter 必须产生换行且不触发 form submit；IME 候选确认不触发 Run；发送按钮
  在窄屏详情区展开/收起两种状态下均保持可见可点击。
- 前端质量：`npm run lint`、`npm run typecheck`、`npm test`。
- 浏览器 smoke：在聊天输入多行英文，确认 Enter 不发送；用快捷键发送；运行中观察自动
  跟随，手动上翻后确认位置保持且按钮可用。
- 浏览器 smoke：在桌面和窄屏聊天视图中滚动多条历史，确认滚动条位于对话历史、外层页面滚动
  位置和顶部/输入区保持不动；在历史区滚到边界后继续滚动，确认外层框架不被带动。
