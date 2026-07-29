"""Deterministic demo topology for first-run discovery and smoke tests."""

from __future__ import annotations

from .models import (
    AgentInstance,
    AgentSpec,
    ChildMount,
    ExecutionPolicy,
    MiddlewareBinding,
    ModelBinding,
    ToolBinding,
)
from .storage import SQLiteRepository


async def seed_demo_data(repository: SQLiteRepository, tenant_id: str = "default") -> None:
    if await repository.count_agents(tenant_id):
        return

    analyst = AgentSpec(
        id="agt_market_analyst",
        tenant_id=tenant_id,
        name="市场分析 Agent",
        description="负责把研究问题拆成结构化结论与可核验假设。",
        system_prompt=(
            "你是严谨的市场分析子 Agent。只输出可追踪结论，明确事实、推断与未知项。"
        ),
        model=ModelBinding(provider="mock", model="deterministic"),
        tools=[ToolBinding(plugin_id="tool.calculator", alias="calculator")],
        middlewares=[
            MiddlewareBinding(
                plugin_id="middleware.audit_tags",
                config={"tags": {"role": "analyst"}},
            )
        ],
        policy=ExecutionPolicy(max_steps=6, max_depth=2, max_tool_calls=8),
        labels={"team": "research", "tier": "worker"},
    )
    verifier = AgentSpec(
        id="agt_fact_verifier",
        tenant_id=tenant_id,
        name="事实校验 Agent",
        description="检查证据强度、冲突与遗漏。",
        system_prompt=(
            "你是事实校验子 Agent。标注证据等级、冲突点与仍需验证的内容，不虚构来源。"
        ),
        model=ModelBinding(provider="mock", model="deterministic"),
        tools=[ToolBinding(plugin_id="tool.utc_now", alias="utc_now")],
        policy=ExecutionPolicy(max_steps=6, max_depth=2, max_tool_calls=8),
        labels={"team": "research", "tier": "worker"},
    )
    await repository.save_agent(tenant_id, analyst)
    await repository.save_agent(tenant_id, verifier)

    lead = AgentSpec(
        id="agt_research_lead",
        tenant_id=tenant_id,
        name="研究负责人 Agent",
        description="按需调用分析与校验子 Agent，并汇总最终结果。",
        system_prompt=(
            "你是研究团队负责人。将合适的子任务委派给已挂载 Agent，"
            "遵守预算和深度限制，并清晰汇总结果。"
        ),
        model=ModelBinding(provider="mock", model="deterministic"),
        children=[
            ChildMount(
                alias="analyst",
                agent_id=analyst.id,
                description="进行结构化市场与数据分析",
                allowed_tools=["tool.calculator"],
                max_concurrency=2,
            ),
            ChildMount(
                alias="verifier",
                agent_id=verifier.id,
                description="校验事实、证据和结论边界",
                allowed_tools=["tool.utc_now"],
                max_concurrency=2,
            ),
        ],
        tools=[ToolBinding(plugin_id="tool.echo", alias="echo")],
        policy=ExecutionPolicy(
            max_steps=16,
            max_depth=4,
            max_tool_calls=24,
            max_parallel_children=4,
            token_budget=32_000,
        ),
        labels={"team": "research", "tier": "leader"},
    )
    saved_lead = await repository.save_agent(tenant_id, lead)
    await repository.save_instance(
        tenant_id,
        AgentInstance(
            id="ins_research_local",
            tenant_id=tenant_id,
            name="研究团队 · 本地",
            agent_id=saved_lead.id,
            agent_revision=saved_lead.revision,
            environment="local",
            max_concurrency=4,
        ),
    )
