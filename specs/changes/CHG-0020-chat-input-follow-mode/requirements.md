---
kind: requirements-delta
id: CHG-0020-REQUIREMENTS
status: accepted
target: 0.1
---

# Requirements delta

## CHAT-017 — 安全的对话提交快捷键

WHEN the Agent chat composer has focus
THE SYSTEM SHALL insert a newline for plain `Enter` and SHALL submit only on `⌘/Ctrl + Enter`
or the explicit 发送 button.

WHEN a keyboard event is part of an IME composition
THE SYSTEM SHALL not submit the Run from that composition-confirmation event.

## CHAT-018 — 对话区跟随与历史阅读

WHEN the chat thread is at or near its bottom
THE SYSTEM SHALL automatically keep the latest message and streaming delta visible.

WHEN the user scrolls materially above the bottom
THE SYSTEM SHALL pause automatic following and present a keyboard-accessible “回到底部” action;
activating it SHALL restore following and reveal the latest content.

## CHAT-019 — 聊天视图滚动边界

WHEN the Agent chat view is open
THE SYSTEM SHALL keep the application chrome, chat header, composer, sidebar and inspector within
the viewport; only the conversation history SHALL own the primary vertical scroll. Responsive layouts
MAY stack the sidebar and inspector, but SHALL keep them inside the fixed chat viewport.

The chat history scroll container SHALL contain its overscroll so reaching its boundary does not
scroll the outer application frame.
