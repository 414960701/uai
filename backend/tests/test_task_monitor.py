from uai_forge.interactions import extract_choice_prompt
from uai_forge.tasks import (
    build_task_todo_list,
    is_complex_task,
    mark_todo_running,
    mark_todo_terminal,
)
from uai_forge.models import TodoStatus


def test_complexity_heuristic_only_adds_todo_for_multi_step_requests():
    assert is_complex_task("你好，简单介绍一下你自己") is False
    assert is_complex_task(
        "请分析当前方案并比较两个实现路径，然后整理风险、测试步骤和最终交付建议。"
    ) is True

    todo = build_task_todo_list(
        run_id="run_complex",
        session_id="session_complex",
        input_text="请分析当前方案并比较两个实现路径，然后整理风险、测试步骤和最终交付建议。",
    )
    assert todo is not None
    assert todo.source == "automatic"
    assert todo.status is TodoStatus.PENDING
    assert len(todo.items) >= 2
    inferred_titles = [item.title for item in todo.items]
    assert "收集并分析相关信息" in inferred_titles
    assert "比较并评估候选方案" in inferred_titles
    assert "验证结果与边界" in inferred_titles
    assert len(inferred_titles) <= 6
    assert "当前方案" not in todo.title

    running = mark_todo_running(todo)
    assert running.status is TodoStatus.RUNNING
    assert running.items[0].status is TodoStatus.RUNNING
    completed = mark_todo_terminal(running, TodoStatus.COMPLETED)
    assert completed.status is TodoStatus.COMPLETED
    assert all(item.status is TodoStatus.COMPLETED for item in completed.items)


def test_choice_marker_is_public_and_safe_to_render():
    output = (
        "我需要确认偏好。\n"
        '<!-- uai-choice:{"title":"选择风格","description":"用于下一步输出",'
        '"selection_type":"single","required":true,"options":['
        '{"id":"clean","label":"简洁","description":"信息密度低","recommended":true},'
        '{"id":"detail","label":"详细","description":"包含更多解释"}]} -->'
    )
    cleaned, choice = extract_choice_prompt(output=output, run_id="run_choice")
    assert cleaned == "我需要确认偏好。"
    assert choice is not None
    assert choice.run_id == "run_choice"
    assert choice.options[0].recommended is True
    assert choice.status == "open"


def test_choice_marker_rejects_inline_credentials():
    output = (
        '<!-- uai-choice:{"title":"选择","options":['
        '{"id":"bad","label":"泄露","description":"api_key: secret"},'
        '{"id":"ok","label":"安全"}]} -->'
    )
    cleaned, choice = extract_choice_prompt(output=output, run_id="run_choice_secret")
    assert cleaned == output
    assert choice is None
