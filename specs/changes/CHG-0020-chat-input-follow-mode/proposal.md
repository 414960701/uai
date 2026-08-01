---
kind: change-proposal
id: CHG-0020
status: specified
target: 0.1
date: 2026-08-01
implementation_status: in_progress
requirements:
  - CHAT-017
  - CHAT-018
---

# 对话输入与跟随滚动

对话输入框当前把普通 Enter 直接解释为发送，既不适合多行英文内容，也会在输入法确认候选
词时误触发提交；消息增量变多后，用户还需要手动拖动对话区到底部。

本变更把普通 Enter 改为换行，以 `⌘/Ctrl + Enter` 发送，并忽略 IME composing 状态；
对话区默认跟随最新内容，用户主动上翻后暂停跟随并提供回到底部入口。
