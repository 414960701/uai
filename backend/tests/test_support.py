"""Test-only provider and topology helpers.

The product runtime intentionally ships only real provider adapters.  Tests use
this isolated provider instead of making a test provider part of the framework
registry or control-plane catalog.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import AsyncIterator, List

from uai_forge.models import (
    AgentInstance,
    AgentSpec,
    ChildMount,
    ExecutionPolicy,
    MiddlewareBinding,
    ModelBinding,
    ModelConfig,
    PluginKind,
    PluginManifest,
    ToolBinding,
)
from uai_forge.ports import ModelMessage, ModelOutput, ModelProvider, ModelRequest, ModelStreamChunk, TokenUsage, ToolCall
from uai_forge.registry import PluginRegistry
from uai_forge.storage import SQLiteRepository


TEST_PROVIDER_ID = "test.deterministic"
TEST_MODEL_ID = "deterministic"
TEST_PROVIDER_MANIFEST = PluginManifest(
    id=TEST_PROVIDER_ID,
    kind=PluginKind.PROVIDER,
    display_name="Deterministic test provider",
    version="1.0.0",
    description="Test-only provider; never registered by the product runtime.",
    capabilities=["tool_calling", "parallel_safe", "usage_estimate"],
    config_schema={"type": "object", "additionalProperties": False},
)


class DeterministicTestProvider(ModelProvider):
    manifest = TEST_PROVIDER_MANIFEST

    def __init__(self, manifest: PluginManifest = TEST_PROVIDER_MANIFEST):
        self.manifest = manifest

    @staticmethod
    def _estimate_tokens(messages: List[ModelMessage], output: str) -> TokenUsage:
        input_chars = sum(len(message.content or "") for message in messages)
        return TokenUsage(
            input_tokens=max(1, input_chars // 4),
            output_tokens=max(1, len(output) // 4),
        )

    async def complete(self, request: ModelRequest) -> ModelOutput:
        last = request.messages[-1]
        if last.role == "tool":
            output = f"已完成协作，结果：{last.content or ''}"
            return ModelOutput(
                content=output,
                usage=self._estimate_tokens(request.messages, output),
            )

        user_text = next(
            (
                message.content or ""
                for message in reversed(request.messages)
                if message.role == "user"
            ),
            "",
        )
        available = {
            item.get("function", {}).get("name")
            for item in request.tools
            if item.get("function", {}).get("name")
        }

        delegate = re.search(r"delegate:([a-z][a-z0-9_-]*)\s+(.+)", user_text, re.DOTALL)
        if delegate:
            tool_name = f"delegate_{delegate.group(1)}"
            if tool_name in available:
                return ModelOutput(
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:12]}",
                            name=tool_name,
                            arguments={"input": delegate.group(2).strip()},
                        )
                    ],
                    usage=self._estimate_tokens(request.messages, ""),
                )

        explicit_tool = re.search(r"tool:([a-zA-Z0-9_.-]+)\s+(.+)", user_text, re.DOTALL)
        if explicit_tool:
            requested = explicit_tool.group(1).replace(".", "_").replace("-", "_")
            if requested in available:
                raw_arguments = explicit_tool.group(2).strip()
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    arguments = {"input": raw_arguments, "expression": raw_arguments}
                return ModelOutput(
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:12]}",
                            name=requested,
                            arguments=arguments,
                        )
                    ],
                    usage=self._estimate_tokens(request.messages, ""),
                )

        agent_name = request.metadata.get("agent_name", "Agent")
        output = f"{agent_name}：{user_text}"
        return ModelOutput(
            content=output,
            usage=self._estimate_tokens(request.messages, output),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        output = await self.complete(request)
        midpoint = max(1, len(output.content) // 2)
        yield ModelStreamChunk(text=output.content[:midpoint])
        yield ModelStreamChunk(text=output.content[midpoint:], usage=output.usage)


def register_test_provider(
    registry: PluginRegistry,
    provider_id: str = TEST_PROVIDER_ID,
    streaming: bool = False,
) -> None:
    manifest = (
        TEST_PROVIDER_MANIFEST
        if provider_id == TEST_PROVIDER_ID
        else TEST_PROVIDER_MANIFEST.model_copy(
            update={
                "id": provider_id,
                "display_name": f"Deterministic test provider ({provider_id})",
            }
        )
    )
    if streaming and "streaming" not in manifest.capabilities:
        manifest = manifest.model_copy(update={"capabilities": [*manifest.capabilities, "streaming"]})
    key = (PluginKind.PROVIDER, provider_id)
    if key in registry._manifests:  # type: ignore[attr-defined]
        registry._manifests.pop(key)  # type: ignore[attr-defined]
        registry._config_validators.pop(key, None)  # type: ignore[attr-defined]
        registry._providers.pop(provider_id, None)  # type: ignore[attr-defined]
    registry.register_provider(manifest, lambda binding, selected=manifest: DeterministicTestProvider(selected))


async def seed_test_topology(repository: SQLiteRepository, tenant_id: str = "default") -> None:
    profile = ModelConfig(
        id="mdl_test_default",
        tenant_id=tenant_id,
        name="Deterministic test profile",
        provider=TEST_PROVIDER_ID,
        protocol="test_deterministic",
        model=TEST_MODEL_ID,
        config={},
    )
    await repository.save_model_config(tenant_id, profile)

    analyst = AgentSpec(
        id="agt_market_analyst",
        tenant_id=tenant_id,
        name="市场分析 Agent",
        description="负责把研究问题拆成结构化结论与可核验假设。",
        system_prompt="你是严谨的市场分析子 Agent。只输出可追踪结论。",
        model=ModelBinding(
            model_config_id=profile.id,
        ),
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
        system_prompt="你是事实校验子 Agent。标注证据等级，不虚构来源。",
        model=ModelBinding(
            model_config_id=profile.id,
        ),
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
        system_prompt="你是研究团队负责人。将合适的子任务委派给已挂载 Agent。",
        model=ModelBinding(
            model_config_id=profile.id,
        ),
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
