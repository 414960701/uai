import asyncio
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.models import (
    AgentSpec,
    ChildMount,
    EventType,
    ExecutionPolicy,
    ModelBinding,
    PluginKind,
    PluginManifest,
    RunRequest,
    RunStatus,
    ToolBinding,
)
from uai_forge.ports import ModelOutput, TokenUsage, ToolCall
from uai_forge.registry import PluginRegistry
from uai_forge.run_manager import RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.storage import SQLiteRepository


async def make_runtime(tmp_path: Path):
    repository = SQLiteRepository(str(tmp_path / "multi-agent-policy.db"))
    await repository.initialize()
    registry = PluginRegistry()
    register_builtins(registry)
    events = EventBroker(repository)
    validator = AgentGraphValidator(repository)
    runtime = AgentRuntime(repository, registry, events)
    manager = RunManager(repository, runtime, events, validator)
    return repository, registry, manager


def register_provider(registry, provider_id, factory):
    registry.register_provider(
        PluginManifest(
            id=provider_id,
            kind=PluginKind.PROVIDER,
            display_name=f"Test provider {provider_id}",
            capabilities=["test_only"],
        ),
        factory,
    )


def root_policy(**changes):
    values = {
        "max_steps": 24,
        "max_depth": 6,
        "max_tool_calls": 24,
        "max_parallel_children": 8,
        "timeout_seconds": 2,
        "token_budget": 100_000,
    }
    values.update(changes)
    return ExecutionPolicy(**values)


class ForcedToolCallProvider:
    def __init__(self, call_name, arguments, seen_definitions=None):
        self.call_name = call_name
        self.arguments = arguments
        self.seen_definitions = seen_definitions

    async def complete(self, request):
        names = {
            item.get("function", {}).get("name")
            for item in request.tools
        }
        if self.seen_definitions is not None:
            self.seen_definitions.append(names)
        if request.messages[-1].role == "tool":
            return ModelOutput(
                content="forced tool completed",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )
        return ModelOutput(
            tool_calls=[
                ToolCall(
                    id="call_forced_scope",
                    name=self.call_name,
                    arguments=self.arguments,
                )
            ],
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("child_policy", "child_input", "expected_error"),
    [
        (
            ExecutionPolicy(
                max_steps=1,
                max_depth=2,
                max_tool_calls=4,
                token_budget=10_000,
            ),
            'tool:echo {"input": "needs a second model step"}',
            "reached local step limit 1",
        ),
        (
            ExecutionPolicy(
                max_steps=4,
                max_depth=2,
                max_tool_calls=0,
                token_budget=10_000,
            ),
            'tool:echo {"input": "must not start"}',
            "local tool-call budget exhausted",
        ),
        (
            ExecutionPolicy(
                max_steps=4,
                max_depth=2,
                max_tool_calls=4,
                token_budget=1,
            ),
            "consume more than one token",
            "local token budget exhausted",
        ),
    ],
)
async def test_child_invocation_enforces_local_step_tool_and_token_limits(
    tmp_path,
    child_policy,
    child_input,
    expected_error,
):
    repository, _, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_local_budget_child",
            name="Local Budget Child",
            system_prompt="Use the requested tool.",
            tools=[ToolBinding(plugin_id="tool.echo", alias="echo")],
            policy=child_policy,
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_local_budget_parent",
            name="Local Budget Parent",
            system_prompt="Delegate the task.",
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=root_policy(),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=parent.id,
            input=f"delegate:child {child_input}",
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert expected_error in (finished.error or "")
    if child_policy.max_tool_calls == 0:
        assert all(
            not (
                event.type == EventType.TOOL_STARTED
                and event.agent_id == child.id
            )
            for event in events
        )
    if child_policy.token_budget == 1:
        budget_event = next(
            event
            for event in reversed(events)
            if event.type == EventType.BUDGET_UPDATED
            and event.agent_id == child.id
        )
        assert budget_event.payload["tokens"] > 0
        assert budget_event.payload["local"]["tokens"] > 1


@pytest.mark.asyncio
async def test_child_timeout_cancels_and_releases_all_concurrency_permits(tmp_path):
    repository, registry, manager = await make_runtime(tmp_path)
    state = {"calls": 0}

    class FirstSlowProvider:
        async def complete(self, request):
            state["calls"] += 1
            if state["calls"] == 1:
                await asyncio.sleep(0.5)
            return ModelOutput(
                content="child completed",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )

    register_provider(
        registry,
        "test.first_slow",
        lambda binding: FirstSlowProvider(),
    )
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_timeout_child",
            name="Timeout Child",
            system_prompt="Complete the task.",
            model=ModelBinding(provider="test.first_slow", model="slow"),
            policy=ExecutionPolicy(timeout_seconds=0.03),
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_timeout_parent",
            name="Timeout Parent",
            system_prompt="Delegate the task.",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child.id,
                    max_concurrency=1,
                )
            ],
            policy=root_policy(max_parallel_children=1),
        ),
    )

    started = time.monotonic()
    first_run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:child first attempt"),
    )
    first = await manager.wait("default", first_run.id)
    elapsed = time.monotonic() - started

    assert first.status == RunStatus.FAILED
    assert "exceeded local timeout 0.03s" in (first.error or "")
    assert elapsed < 0.3

    second_run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:child second attempt"),
    )
    second = await asyncio.wait_for(
        manager.wait("default", second_run.id),
        timeout=0.5,
    )
    assert second.status == RunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_child_local_parallel_limit_caps_grandchild_fanout(tmp_path):
    repository, registry, manager = await make_runtime(tmp_path)
    tracker = {"active": 0, "peak": 0}
    tracker_lock = asyncio.Lock()

    class FanOutProvider:
        async def complete(self, request):
            if request.messages[-1].role == "tool":
                return ModelOutput(
                    content="fanout completed",
                    usage=TokenUsage(input_tokens=1, output_tokens=1),
                )
            return ModelOutput(
                tool_calls=[
                    ToolCall(
                        id=f"call_leaf_{index}",
                        name="delegate_leaf",
                        arguments={"input": f"leaf {index}"},
                    )
                    for index in range(3)
                ],
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )

    class TrackingLeafProvider:
        async def complete(self, request):
            async with tracker_lock:
                tracker["active"] += 1
                tracker["peak"] = max(tracker["peak"], tracker["active"])
            try:
                await asyncio.sleep(0.03)
                return ModelOutput(
                    content="leaf completed",
                    usage=TokenUsage(input_tokens=1, output_tokens=1),
                )
            finally:
                async with tracker_lock:
                    tracker["active"] -= 1

    register_provider(registry, "test.fanout", lambda binding: FanOutProvider())
    register_provider(
        registry,
        "test.tracking_leaf",
        lambda binding: TrackingLeafProvider(),
    )
    leaf = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_parallel_leaf",
            name="Parallel Leaf",
            system_prompt="Complete the leaf task.",
            model=ModelBinding(provider="test.tracking_leaf", model="leaf"),
            policy=ExecutionPolicy(timeout_seconds=1),
        ),
    )
    middle = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_parallel_middle",
            name="Parallel Middle",
            system_prompt="Fan out.",
            model=ModelBinding(provider="test.fanout", model="fanout"),
            children=[
                ChildMount(
                    alias="leaf",
                    agent_id=leaf.id,
                    max_concurrency=8,
                )
            ],
            policy=ExecutionPolicy(
                max_steps=4,
                max_depth=3,
                max_tool_calls=8,
                max_parallel_children=1,
                timeout_seconds=1,
                token_budget=10_000,
            ),
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_parallel_parent",
            name="Parallel Parent",
            system_prompt="Delegate to the middle.",
            children=[
                ChildMount(
                    alias="middle",
                    agent_id=middle.id,
                    max_concurrency=8,
                )
            ],
            policy=root_policy(max_parallel_children=4),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:middle fan out now"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert tracker["peak"] == 1
    assert tracker["active"] == 0


@pytest.mark.asyncio
async def test_child_local_depth_zero_blocks_its_own_delegation(tmp_path):
    repository, _, manager = await make_runtime(tmp_path)
    leaf = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_depth_leaf",
            name="Depth Leaf",
            system_prompt="Complete the leaf task.",
        ),
    )
    middle = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_depth_middle",
            name="Depth Middle",
            system_prompt="Delegate to the leaf.",
            children=[ChildMount(alias="leaf", agent_id=leaf.id)],
            policy=ExecutionPolicy(max_depth=0),
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_depth_parent",
            name="Depth Parent",
            system_prompt="Delegate to the middle.",
            children=[ChildMount(alias="middle", agent_id=middle.id)],
            policy=root_policy(max_depth=5),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=parent.id,
            input="delegate:middle delegate:leaf must be blocked",
        ),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "maximum effective delegation depth 1 exceeded" in (
        finished.error or ""
    )


@pytest.mark.asyncio
async def test_child_local_tool_limit_also_blocks_delegation_calls(tmp_path):
    repository, _, manager = await make_runtime(tmp_path)
    leaf = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_tool_limit_leaf",
            name="Tool Limit Leaf",
            system_prompt="Complete the leaf task.",
        ),
    )
    middle = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_tool_limit_middle",
            name="Tool Limit Middle",
            system_prompt="Delegate to the leaf.",
            children=[ChildMount(alias="leaf", agent_id=leaf.id)],
            policy=ExecutionPolicy(max_tool_calls=0),
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_tool_limit_parent",
            name="Tool Limit Parent",
            system_prompt="Delegate to the middle.",
            children=[ChildMount(alias="middle", agent_id=middle.id)],
            policy=root_policy(),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=parent.id,
            input="delegate:middle delegate:leaf must not start",
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "agent agt_tool_limit_middle local tool-call budget exhausted" in (
        finished.error or ""
    )
    assert all(
        not (
            event.type == EventType.DELEGATION_STARTED
            and event.agent_id == middle.id
        )
        for event in events
    )


@pytest.mark.asyncio
async def test_mount_allowlist_null_is_compatible_and_empty_denies_all_tools(
    tmp_path,
    monkeypatch,
):
    repository, registry, manager = await make_runtime(tmp_path)
    seen_definitions = []
    constructed_plugins = []
    register_provider(
        registry,
        "test.forced_echo",
        lambda binding: ForcedToolCallProvider(
            "echo",
            {"input": "scope probe"},
            seen_definitions,
        ),
    )
    original_create_tool = registry.create_tool

    def capture_create_tool(binding):
        constructed_plugins.append(binding.plugin_id)
        return original_create_tool(binding)

    monkeypatch.setattr(registry, "create_tool", capture_create_tool)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_echo_child",
            name="Scope Echo Child",
            system_prompt="Call echo.",
            model=ModelBinding(provider="test.forced_echo", model="forced"),
            tools=[ToolBinding(plugin_id="tool.echo", alias="echo")],
        ),
    )
    legacy_parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_legacy_parent",
            name="Scope Legacy Parent",
            system_prompt="Delegate.",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child.id,
                    allowed_tools=None,
                )
            ],
            policy=root_policy(),
        ),
    )
    empty_parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_empty_parent",
            name="Scope Empty Parent",
            system_prompt="Delegate.",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child.id,
                    allowed_tools=[],
                )
            ],
            policy=root_policy(),
        ),
    )
    allowed_parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_allowed_parent",
            name="Scope Allowed Parent",
            system_prompt="Delegate.",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child.id,
                    allowed_tools=["tool.echo"],
                )
            ],
            policy=root_policy(),
        ),
    )

    legacy_run = await manager.start(
        "default",
        RunRequest(agent_id=legacy_parent.id, input="delegate:child use echo"),
    )
    legacy = await manager.wait("default", legacy_run.id)
    assert legacy.status == RunStatus.SUCCEEDED
    assert "tool.echo" in constructed_plugins
    assert any("echo" in definitions for definitions in seen_definitions)

    constructed_plugins.clear()
    seen_definitions.clear()
    allowed_run = await manager.start(
        "default",
        RunRequest(agent_id=allowed_parent.id, input="delegate:child use echo"),
    )
    allowed = await manager.wait("default", allowed_run.id)
    assert allowed.status == RunStatus.SUCCEEDED
    assert constructed_plugins == ["tool.echo"]
    assert any("echo" in definitions for definitions in seen_definitions)

    constructed_plugins.clear()
    seen_definitions.clear()
    empty_run = await manager.start(
        "default",
        RunRequest(agent_id=empty_parent.id, input="delegate:child use echo"),
    )
    empty = await manager.wait("default", empty_run.id)
    empty_events = await repository.list_events("default", empty_run.id)

    assert empty.status == RunStatus.FAILED
    assert "tool outside effective mount scope: tool.echo" in (
        empty.error or ""
    )
    assert constructed_plugins == []
    assert seen_definitions and "echo" not in seen_definitions[0]
    assert all(event.type != EventType.TOOL_STARTED for event in empty_events)


@pytest.mark.asyncio
async def test_descendant_mount_cannot_expand_ancestor_tool_scope(tmp_path):
    repository, registry, manager = await make_runtime(tmp_path)
    seen_definitions = []
    register_provider(
        registry,
        "test.forced_calculator",
        lambda binding: ForcedToolCallProvider(
            "calculator",
            {"expression": "1 + 1"},
            seen_definitions,
        ),
    )
    leaf = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_leaf",
            name="Scope Leaf",
            system_prompt="Call calculator.",
            model=ModelBinding(
                provider="test.forced_calculator",
                model="forced",
            ),
            tools=[
                ToolBinding(
                    plugin_id="tool.calculator",
                    alias="calculator",
                )
            ],
        ),
    )
    middle = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_middle",
            name="Scope Middle",
            system_prompt="Delegate to the leaf.",
            children=[
                ChildMount(
                    alias="leaf",
                    agent_id=leaf.id,
                    allowed_tools=["tool.echo", "tool.calculator"],
                )
            ],
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_parent",
            name="Scope Parent",
            system_prompt="Delegate to the middle.",
            children=[
                ChildMount(
                    alias="middle",
                    agent_id=middle.id,
                    allowed_tools=["tool.echo"],
                )
            ],
            policy=root_policy(),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=parent.id,
            input=(
                "delegate:middle "
                "delegate:leaf tool:calculator {\"expression\": \"1 + 1\"}"
            ),
        ),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "tool outside effective mount scope: tool.calculator" in (
        finished.error or ""
    )
    assert seen_definitions and "calculator" not in seen_definitions[0]


@pytest.mark.asyncio
async def test_mount_allowlist_cannot_upgrade_child_deny_policy(
    tmp_path,
    monkeypatch,
):
    repository, registry, manager = await make_runtime(tmp_path)
    constructed_plugins = []
    original_create_tool = registry.create_tool

    def capture_create_tool(binding):
        constructed_plugins.append(binding.plugin_id)
        return original_create_tool(binding)

    monkeypatch.setattr(registry, "create_tool", capture_create_tool)
    register_provider(
        registry,
        "test.forced_denied_echo",
        lambda binding: ForcedToolCallProvider(
            "echo",
            {"input": "must remain denied"},
        ),
    )
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_denied_child",
            name="Scope Denied Child",
            system_prompt="Attempt echo.",
            model=ModelBinding(
                provider="test.forced_denied_echo",
                model="forced",
            ),
            tools=[
                ToolBinding(
                    plugin_id="tool.echo",
                    alias="echo",
                    permission="deny",
                )
            ],
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_scope_denied_parent",
            name="Scope Denied Parent",
            system_prompt="Delegate.",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child.id,
                    allowed_tools=["tool.echo"],
                )
            ],
            policy=root_policy(),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:child try echo"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "tool policy denied: echo" in (finished.error or "")
    assert constructed_plugins == []
    assert all(event.type != EventType.TOOL_STARTED for event in events)


def test_child_mount_allowed_tools_contract_rejects_ambiguous_values():
    assert ChildMount(
        alias="child",
        agent_id="agt_child",
    ).allowed_tools is None
    assert ChildMount(
        alias="child",
        agent_id="agt_child",
        allowed_tools=[],
    ).allowed_tools == []

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        ChildMount(
            alias="child",
            agent_id="agt_child",
            allowed_tools=["tool.echo", "tool.echo"],
        )
    with pytest.raises(ValidationError, match="lowercase plugin IDs"):
        ChildMount(
            alias="child",
            agent_id="agt_child",
            allowed_tools=["Tool.Echo"],
        )
