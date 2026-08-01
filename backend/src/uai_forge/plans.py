"""Provider-neutral planning artifacts for the review-before-execute flow.

The planner output is intentionally kept as a public, structured summary.  It
is not a transcript of hidden model reasoning and it does not contain provider
objects or credentials.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from .models import ExecutionPlan, PlanStep, PlanStepStatus, PlanStatus, utc_now


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)、])\s+(.+?)\s*$")
_CHINESE_STEP_RE = re.compile(r"^\s*(?:第[一二三四五六七八九十百]+步|步骤\s*\d+)\s*[:：、.]?\s*(.+?)\s*$")
_SECTION_ALIASES = {
    "goal": {"目标", "目的", "goal", "objective", "purpose"},
    "assumptions": {"假设", "前提", "assumptions", "assumption"},
    "steps": {"步骤", "执行步骤", "实施步骤", "计划", "steps", "implementation"},
    "risks": {"风险", "注意事项", "risks", "risk", "限制", "constraints"},
}


def _normalize_heading(value: str) -> str:
    normalized = re.sub(r"[：:。.!！?？]+$", "", value.strip()).lower()
    return re.sub(r"\s+", " ", normalized)


def _section_lines(lines: Sequence[str], section: str) -> List[str]:
    aliases = {_normalize_heading(item) for item in _SECTION_ALIASES[section]}
    start = None
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        heading = _normalize_heading(match.group(1)) if match else _normalize_heading(line)
        if heading in aliases:
            start = index + 1
            break
    if start is None:
        return []
    result: List[str] = []
    for line in lines[start:]:
        if _HEADING_RE.match(line):
            break
        result.append(line)
    return result


def _list_items(lines: Iterable[str]) -> List[str]:
    result: List[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        match = _LIST_RE.match(line) or _CHINESE_STEP_RE.match(line)
        value = match.group(1).strip() if match else line
        value = re.sub(r"[*_`~]+", "", value)
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in result:
            result.append(value[:1_000])
    return result[:12]


def _step_items(lines: Sequence[str], output: str) -> List[str]:
    explicit = _list_items(lines)
    if explicit:
        return explicit

    numbered = _list_items(output.splitlines())
    if numbered:
        return numbered

    paragraphs = [
        re.sub(r"\s+", " ", item.strip())
        for item in re.split(r"\n\s*\n|(?<=[。！？!?])\s+", output)
        if item.strip()
    ]
    return [item[:1_000] for item in paragraphs[:6]]


def _risk_level(description: str) -> str:
    if re.search(r"删除|清空|不可逆|生产|部署|权限|外部写入|delete|destroy|deploy|permission", description, re.I):
        return "high"
    if re.search(r"网络|依赖|兼容|数据|验证|network|dependency|migration", description, re.I):
        return "medium"
    return "low"


def _step_scope(description: str) -> List[str]:
    references = re.findall(r"`([^`]{1,160})`", description)
    return list(dict.fromkeys(references))[:8]


def build_execution_plan(
    *,
    run_id: str,
    session_id: str,
    input_text: str,
    output: str,
) -> ExecutionPlan:
    """Convert the model's public plan prose into a reviewable plan object.

    Models are asked to use headings and ordered bullets, but this parser keeps
    the contract useful for providers that return ordinary prose.  When the
    model lacks repository facts, that uncertainty remains visible as an
    assumption rather than being invented as a tool result.
    """

    lines = output.splitlines()
    heading = next(
        (match.group(1).strip() for line in lines if (match := _HEADING_RE.match(line))),
        "执行计划",
    )
    heading = re.sub(r"^计划(?:模式)?[：:]\s*", "", heading).strip() or "执行计划"

    goal_lines = _section_lines(lines, "goal")
    goal = " ".join(item.strip() for item in goal_lines if item.strip()) or input_text.strip()
    assumptions = _list_items(_section_lines(lines, "assumptions"))
    if not assumptions:
        assumptions = ["当前计划基于 Agent 已配置的上下文与权限；未验证的事实会在执行阶段重新确认。"]

    step_texts = _step_items(_section_lines(lines, "steps"), output)
    if not step_texts:
        step_texts = ["澄清目标、确认执行边界，并在获得批准后开始执行。"]
    step_texts = [re.sub(r"[*_`~]+", "", text).strip() for text in step_texts]
    steps = [
        PlanStep(
            id=f"step_{index:02d}",
            title=(text.split("：", 1)[0] if "：" in text and len(text.split("：", 1)[0]) <= 60 else text[:60]),
            description=text,
            scope=_step_scope(text),
            risk=_risk_level(text),
            status=PlanStepStatus.PROPOSED,
        )
        for index, text in enumerate(step_texts, start=1)
    ]

    risks = _list_items(_section_lines(lines, "risks"))
    if not risks:
        risks = ["执行前需要再次确认步骤范围、外部副作用和可用权限。"]

    now = utc_now()
    return ExecutionPlan(
        run_id=run_id,
        session_id=session_id,
        title=heading[:200],
        goal=goal[:2_000],
        assumptions=assumptions,
        steps=steps,
        risks=risks,
        status=PlanStatus.PROPOSED,
        created_at=now,
        updated_at=now,
    )
