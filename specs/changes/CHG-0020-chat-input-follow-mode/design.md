---
kind: design-delta
id: CHG-0020-DESIGN
status: implemented
target: 0.1
---

# 输入与跟随滚动设计

- `textarea` 保留浏览器原生换行行为；只有 `metaKey` 或 `ctrlKey` 与 Enter 同时出现时才
  `requestSubmit()`，`nativeEvent.isComposing` 优先阻断提交。
- `chat-thread` 使用独立的 scroll ref 和 near-bottom threshold。Run 切换、历史回放、事件
  增量和正文增量在“跟随中”时通过 `requestAnimationFrame` 定位到底部。
- 用户上翻后不抢夺滚动位置；浮动按钮只在确实存在未读底部内容时出现，点击后恢复跟随。
- `chat-page` 使用视口高度约束；`chat-view-stack` 和 `chat-workspace` 通过
  `minmax(0, 1fr)` 建立完整高度链，`chat-thread` 是唯一的主对话滚动容器，并用
  `overscroll-behavior: contain` 阻断滚动链向外层传播。窄屏将侧栏和详情堆叠在固定聊天
  视口内，输入法弹出时仍由历史区吸收多余滚动。
