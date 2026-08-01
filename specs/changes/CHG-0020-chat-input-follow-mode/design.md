---
kind: design-delta
id: CHG-0020-DESIGN
status: implemented
target: 0.1
---

# 输入与跟随滚动设计

- `textarea` 对 Enter 始终先阻止表单隐式提交：合成输入期间交给 IME 完成候选确认，普通 Enter
  显式插入换行，只有 `metaKey` 或 `ctrlKey` 与 Enter 同时出现时才 `requestSubmit()`。
  `onSubmit` 同时检查 composition guard，防止浏览器在 compositionend 附近产生隐式提交。
- `chat-thread` 使用独立的 scroll ref 和 near-bottom threshold。Run 切换、历史回放、事件
  增量和正文增量在“跟随中”时通过 `requestAnimationFrame` 定位到底部。
- 用户上翻后不抢夺滚动位置；浮动按钮只在确实存在未读底部内容时出现，点击后恢复跟随。
- `chat-page` 使用视口高度约束；`chat-view-stack` 和 `chat-workspace` 通过
  `minmax(0, 1fr)` 建立完整高度链，`chat-thread` 是唯一的主对话滚动容器，并用
  `overscroll-behavior: contain` 阻断滚动链向外层传播。窄屏将侧栏和详情堆叠在固定聊天
  视口内，详情面板在窄屏压缩为自身滚动区域，发送区保持可点击。
