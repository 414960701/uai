"""Provider-neutral task-monitor heuristics and state transitions."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from .models import TaskTodoList, TodoItem, TodoStatus, utc_now


_ACTION_WORDS = (
    "分析", "研究", "实现", "开发", "整理", "比较", "规划", "生成", "调查",
    "修复", "设计", "检查", "部署", "迁移", "总结", "测试", "评估", "审计",
    "analyze", "research", "implement", "build", "compare", "plan", "generate",
    "investigate", "fix", "design", "check", "deploy", "migrate", "summarize",
    "test", "review",
)
_JOIN_WORDS = ("并且", "然后", "最后", "同时", "分别", "以及", "之后", "先", "再", "and", "then")

_ACTION_STAGES = (
    (("研究", "调查", "分析", "research", "investigate", "analyze"), "收集并分析相关信息", "确认背景、输入和关键约束。"),
    (("比较", "评估", "compare", "review"), "比较并评估候选方案", "整理差异、取舍和适用边界。"),
    (("规划", "设计", "plan", "design"), "设计可执行方案", "把目标拆成有顺序的公开执行阶段。"),
    (("实现", "开发", "修复", "部署", "迁移", "implement", "build", "fix", "deploy", "migrate"), "完成核心工作", "按约束执行模型、工具或 Agent 协作。"),
    (("测试", "检查", "验证", "test", "check"), "验证结果与边界", "检查结果、错误路径和安全边界。"),
    (("整理", "总结", "生成", "输出", "summarize", "generate"), "整理最终交付", "汇总发现、产物和下一步建议。"),
)


def _count_matches(value: str, words: Iterable[str]) -> int:
    lowered = value.lower()
    return sum(lowered.count(word.lower()) for word in words)


def is_complex_task(input_text: str) -> bool:
    """Return true only when a TodoList adds signal beyond a simple answer."""

    value = re.sub(r"\s+", " ", input_text.strip())
    if len(value) < 36:
        return False
    action_count = _count_matches(value, _ACTION_WORDS)
    join_count = _count_matches(value, _JOIN_WORDS)
    explicit_steps = bool(re.search(r"(?:步骤|step\s*\d|\d+[.)、])", value, re.I))
    return (
        (action_count >= 2 and (join_count >= 1 or len(value) >= 54))
        or join_count >= 2
        or explicit_steps
        or (len(value) >= 140 and action_count >= 1)
    )


def _inferred_items(input_text: str) -> List[TodoItem]:
    value = input_text.lower()
    items: List[TodoItem] = []
    for words, title, description in _ACTION_STAGES:
        if any(word.lower() in value for word in words):
            items.append(
                TodoItem(
                    id=f"todo_{len(items) + 1:02d}",
                    title=title,
                    description=description,
                    status=TodoStatus.PENDING,
                )
            )
    if len(items) >= 2:
        return items[:6]
    return [
        TodoItem(
            id="todo_01",
            title="明确目标与约束",
            description="确认交付目标、范围和不可执行的边界。",
            status=TodoStatus.PENDING,
        ),
        TodoItem(
            id="todo_02",
            title="分析任务并拆分步骤",
            description="围绕当前请求整理必要的公开执行阶段。",
            status=TodoStatus.PENDING,
        ),
        TodoItem(
            id="todo_03",
            title="完成核心工作",
            description="按约束执行模型、工具或 Agent 协作。",
            status=TodoStatus.PENDING,
        ),
        TodoItem(
            id="todo_04",
            title="校验结果并整理交付",
            description="检查结果、风险和下一步建议，再输出最终答复。",
            status=TodoStatus.PENDING,
        ),
    ]


def build_task_todo_list(*, run_id: str, session_id: str, input_text: str) -> Optional[TaskTodoList]:
    if not is_complex_task(input_text):
        return None
    items = _inferred_items(input_text)
    now = utc_now()
    return TaskTodoList(
        run_id=run_id,
        session_id=session_id,
        title="任务清单 · 多步骤任务",
        items=items,
        status=TodoStatus.PENDING,
        source="automatic",
        created_at=now,
        updated_at=now,
    )


def mark_todo_running(todo: TaskTodoList) -> TaskTodoList:
    items = [
        item.model_copy(update={"status": TodoStatus.RUNNING if index == 0 else TodoStatus.PENDING})
        for index, item in enumerate(todo.items)
    ]
    return todo.model_copy(update={"items": items, "status": TodoStatus.RUNNING, "updated_at": utc_now()})


def mark_todo_terminal(todo: TaskTodoList, status: TodoStatus) -> TaskTodoList:
    if status is TodoStatus.COMPLETED:
        items = [item.model_copy(update={"status": TodoStatus.COMPLETED}) for item in todo.items]
    elif status is TodoStatus.FAILED:
        items = [
            item.model_copy(update={"status": TodoStatus.FAILED if index == 0 else TodoStatus.SKIPPED})
            for index, item in enumerate(todo.items)
        ]
    else:
        items = [
            item.model_copy(update={"status": TodoStatus.SKIPPED if item.status is not TodoStatus.COMPLETED else item.status})
            for item in todo.items
        ]
    return todo.model_copy(update={"items": items, "status": status, "updated_at": utc_now()})
