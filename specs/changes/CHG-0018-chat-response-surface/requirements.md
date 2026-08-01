---
kind: requirements-delta
id: CHG-0018-REQUIREMENTS
status: implemented
target: 0.1
---

# Requirements delta

## CHAT-011 — 连续的回答阅读表面

WHEN the Agent 对话区显示成功、流式、失败或取消的助手消息
THE SYSTEM SHALL keep the assistant answer in one continuous reading surface; the normal
answer SHALL NOT be rendered as a bordered card nested inside another bordered card.

用户消息 MAY 使用轻量背景气泡；助手消息 SHALL 保留 Agent 名称、状态、正文、公开执行阶段
和 Run 详情入口，但这些信息 SHALL 有清晰的视觉层级，不能把稳定诊断字段抢到正文之前。

## CHAT-012 — 安全的正文排版

WHEN the model output contains common Markdown markers for headings, emphasis, lists, inline code,
or paragraphs
THE SYSTEM SHALL render those markers as safe React text elements without interpreting HTML or
executing arbitrary markup.

流式增量和历史回放 SHALL 使用同一套正文投影；投影不改变服务器 output、事件事实或 Trace
payload，也不得展示隐藏思维、完整 prompt、凭证或未脱敏工具参数。

## CHAT-013 — 执行过程与回答解耦

WHEN public reasoning stages exist
THE SYSTEM SHALL present them as a low-emphasis, collapsible activity strip attached to the
assistant message. The strip SHALL show its public-summary boundary and current/terminal state,
while detailed event, span and payload inspection SHALL remain behind the Run inspector action.

## CHAT-014 — 统一的干净控制台表面

WHEN the user navigates between 工作台、Agent 对话、运行记录、扩展和配置页面
THE SYSTEM SHALL use one consistent light surface system for navigation, top bar, panels, controls,
forms and overlays: restrained borders, predictable spacing, readable text hierarchy and limited
accent color.

THE SYSTEM SHALL preserve existing navigation, responsive layout, focus-visible states, reduced-motion
behavior and status/error meaning while changing visual tokens; diagnostic code blocks MAY remain
visually distinct from normal content.
