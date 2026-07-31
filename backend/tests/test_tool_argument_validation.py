from pathlib import Path

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.models import (
    AgentSpec,
    ChildMount,
    EventType,
    ExecutionPolicy,
    MiddlewareBinding,
    ModelBinding,
    PluginKind,
    PluginManifest,
    RunRequest,
    RunStatus,
    ToolBinding,
)
from uai_forge.ports import ModelOutput, TokenUsage, ToolCall, ToolPlugin
from uai_forge.registry import PluginRegistry
from uai_forge.run_manager import RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.storage import SQLiteRepository
from test_support import register_test_provider


class ForcedArgumentsProvider:
    def __init__(self, call_name, arguments):
        self.call_name = call_name
        self.arguments = arguments

    async def complete(self, request):
        if request.messages[-1].role == "tool":
            return ModelOutput(
                content="tool completed",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )
        return ModelOutput(
            tool_calls=[
                ToolCall(
                    id="call_schema_guard",
                    name=self.call_name,
                    arguments=self.arguments,
                )
            ],
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )


def register_forced_provider(
    registry: PluginRegistry,
    provider_id: str,
    call_name: str,
    arguments,
) -> None:
    registry.register_provider(
        PluginManifest(
            id=provider_id,
            kind=PluginKind.PROVIDER,
            display_name=f"Forced provider {provider_id}",
            source="entry_point",
            config_schema={
                "type": "object",
                "additionalProperties": False,
            },
        ),
        lambda binding: ForcedArgumentsProvider(call_name, arguments),
    )


async def make_runtime(tmp_path: Path, filename: str):
    repository = SQLiteRepository(str(tmp_path / filename))
    await repository.initialize()
    registry = PluginRegistry()
    register_builtins(registry)
    register_test_provider(registry, "openai_compatible")
    events = EventBroker(repository)
    runtime = AgentRuntime(repository, registry, events)
    manager = RunManager(
        repository,
        runtime,
        events,
        AgentGraphValidator(repository),
    )
    return repository, registry, manager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_id", "tool", "call_name", "arguments", "keyword", "secret"),
    [
        (
            "provider.missing_argument",
            ToolBinding(plugin_id="tool.echo", alias="guarded"),
            "guarded",
            {},
            "required",
            "",
        ),
        (
            "provider.extra_argument",
            ToolBinding(plugin_id="tool.echo", alias="guarded"),
            "guarded",
            {"input": "ok", "extra": "sensitive-extra-value"},
            "additionalProperties",
            "sensitive-extra-value",
        ),
        (
            "provider.wrong_argument_type",
            ToolBinding(plugin_id="tool.calculator", alias="guarded"),
            "guarded",
            {"expression": 987654321},
            "type",
            "987654321",
        ),
    ],
)
async def test_tool_arguments_reject_required_extra_and_type_before_invoke(
    tmp_path,
    provider_id,
    tool,
    call_name,
    arguments,
    keyword,
    secret,
):
    repository, registry, manager = await make_runtime(
        tmp_path,
        f"{provider_id}.db",
    )
    register_forced_provider(
        registry,
        provider_id,
        call_name,
        arguments,
    )
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id=f"agt_{keyword.lower()}_arguments",
            name=f"{keyword} Arguments",
            system_prompt="Call the configured tool.",
            model=ModelBinding(
                model_config_id=provider_id,
            ),
            tools=[tool],
            policy=ExecutionPolicy(max_steps=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="force invalid arguments"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "tool.arguments_invalid" in (finished.error or "")
    assert f"keyword={keyword}" in (finished.error or "")
    if secret:
        assert secret not in (finished.error or "")
    assert all(event.type != EventType.TOOL_STARTED for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "keyword"),
    [
        ({}, "required"),
        (
            {"input": "ok", "extra": "sensitive-delegation-value"},
            "additionalProperties",
        ),
        ({"input": 42}, "type"),
        ({"input": "x" * 100_001}, "maxLength"),
    ],
)
async def test_delegation_arguments_are_schema_validated_before_child_start(
    tmp_path,
    arguments,
    keyword,
):
    repository, registry, manager = await make_runtime(
        tmp_path,
        f"delegation-{keyword}.db",
    )
    provider_id = f"provider.delegation_{keyword.lower()}"
    register_forced_provider(
        registry,
        provider_id,
        "delegate_child",
        arguments,
    )
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id=f"agt_delegation_child_{keyword.lower()}",
            name="Delegation Child",
            system_prompt="This child must not start.",
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id=f"agt_delegation_parent_{keyword.lower()}",
            name="Delegation Parent",
            system_prompt="Delegate with forced arguments.",
            model=ModelBinding(model_config_id=provider_id),
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=ExecutionPolicy(max_steps=3, max_depth=2),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="force invalid delegation"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "tool.arguments_invalid" in (finished.error or "")
    assert f"keyword={keyword}" in (finished.error or "")
    assert "sensitive-delegation-value" not in (finished.error or "")
    assert all(
        event.type != EventType.DELEGATION_STARTED
        for event in events
    )


@pytest.mark.asyncio
async def test_middleware_mutated_arguments_are_revalidated_before_invoke(tmp_path):
    repository, registry, manager = await make_runtime(
        tmp_path,
        "middleware-argument-validation.db",
    )
    calls = {"invoke": 0}

    class GuardedTool(ToolPlugin):
        name = "guarded"
        description = "Tool with strict arguments."
        parameters = {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
            "additionalProperties": False,
        }

        async def invoke(self, arguments, context):
            calls["invoke"] += 1
            return {"ok": True}

    class MutatingMiddleware:
        async def before_tool(self, context, name, arguments):
            return {
                **arguments,
                "extra": "sensitive-middleware-value",
            }

        async def after_tool(self, context, name, result):
            return result

        async def before_model(self, context, request):
            return request

        async def after_model(self, context, output):
            return output

    registry.register_tool(
        PluginManifest(
            id="tool.guarded_arguments",
            kind=PluginKind.TOOL,
            display_name="Guarded arguments",
            source="entry_point",
            config_schema={
                "type": "object",
                "additionalProperties": False,
            },
        ),
        lambda binding: GuardedTool(),
    )
    registry.register_middleware(
        PluginManifest(
            id="middleware.mutate_arguments",
            kind=PluginKind.MIDDLEWARE,
            display_name="Mutate arguments",
            source="entry_point",
            config_schema={
                "type": "object",
                "additionalProperties": False,
            },
        ),
        lambda binding: MutatingMiddleware(),
    )
    register_forced_provider(
        registry,
        "provider.middleware_arguments",
        "guarded",
        {"input": "initially valid"},
    )
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_middleware_argument_guard",
            name="Middleware Argument Guard",
            system_prompt="Use a middleware-mutated tool call.",
            model=ModelBinding(
                model_config_id="provider.middleware_arguments",
            ),
            tools=[
                ToolBinding(
                    plugin_id="tool.guarded_arguments",
                    alias="guarded",
                )
            ],
            middlewares=[
                MiddlewareBinding(
                    plugin_id="middleware.mutate_arguments",
                )
            ],
            policy=ExecutionPolicy(max_steps=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="mutate arguments"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "tool.arguments_invalid" in (finished.error or "")
    assert "keyword=additionalProperties" in (finished.error or "")
    assert "sensitive-middleware-value" not in (finished.error or "")
    assert calls["invoke"] == 0


@pytest.mark.asyncio
async def test_invalid_tool_parameter_schema_fails_before_provider_call(tmp_path):
    repository, registry, manager = await make_runtime(
        tmp_path,
        "invalid-tool-parameter-schema.db",
    )
    calls = {"provider": 0}

    class InvalidSchemaTool(ToolPlugin):
        name = "invalid_schema"
        description = "Tool with a malformed parameter schema."
        parameters = {"type": "not-a-json-schema-type"}

        async def invoke(self, arguments, context):
            raise AssertionError("invalid-schema tool must never execute")

    class RecordingProvider:
        async def complete(self, request):
            calls["provider"] += 1
            return ModelOutput(content="must not be reached")

    registry.register_tool(
        PluginManifest(
            id="tool.invalid_parameters",
            kind=PluginKind.TOOL,
            display_name="Invalid parameters",
            source="entry_point",
            config_schema={
                "type": "object",
                "additionalProperties": False,
            },
        ),
        lambda binding: InvalidSchemaTool(),
    )
    registry.register_provider(
        PluginManifest(
            id="provider.never_called",
            kind=PluginKind.PROVIDER,
            display_name="Never called",
            source="entry_point",
            config_schema={
                "type": "object",
                "additionalProperties": False,
            },
        ),
        lambda binding: RecordingProvider(),
    )
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_invalid_parameter_schema",
            name="Invalid Parameter Schema",
            system_prompt="Fail before calling the provider.",
            model=ModelBinding(
                model_config_id="provider.never_called",
            ),
            tools=[
                ToolBinding(
                    plugin_id="tool.invalid_parameters",
                    alias="invalid_schema",
                )
            ],
            policy=ExecutionPolicy(max_steps=2),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="do not call provider"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "tool.parameters_schema_invalid" in (finished.error or "")
    assert calls["provider"] == 0
