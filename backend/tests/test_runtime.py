import asyncio
from pathlib import Path

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.models import (
    AgentInstance,
    AgentSpec,
    ChildMount,
    EventType,
    ExecutionPolicy,
    RunEvent,
    RunRequest,
    RunStatus,
    ToolBinding,
)
from uai_forge.registry import PluginRegistry
from uai_forge.run_manager import InvalidTopologyError, RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.storage import SQLiteRepository


async def make_runtime(tmp_path: Path):
    repository = SQLiteRepository(str(tmp_path / "runtime.db"))
    await repository.initialize()
    registry = PluginRegistry()
    register_builtins(registry)
    events = EventBroker(repository)
    validator = AgentGraphValidator(repository)
    runtime = AgentRuntime(repository, registry, events)
    manager = RunManager(repository, runtime, events, validator)
    return repository, manager


@pytest.mark.asyncio
async def test_mounted_agent_executes_as_guarded_tool(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_runtime_child",
            name="Runtime Child",
            system_prompt="Return the delegated task.",
            policy=ExecutionPolicy(max_steps=5),
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_runtime_parent",
            name="Runtime Parent",
            system_prompt="Delegate when requested.",
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=ExecutionPolicy(max_steps=8, max_depth=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:child inspect extensibility"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert "inspect extensibility" in finished.output
    assert any(event.type == EventType.DELEGATION_STARTED for event in events)
    assert any(event.type == EventType.DELEGATION_COMPLETED for event in events)
    assert events[-1].type == EventType.RUN_COMPLETED


@pytest.mark.asyncio
async def test_global_step_budget_covers_child_calls(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(id="agt_budget_child", name="Budget Child", system_prompt="child"),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_budget_parent",
            name="Budget Parent",
            system_prompt="parent",
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=ExecutionPolicy(max_steps=1, max_depth=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:child exceed the shared budget"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert "step budget exhausted" in finished.error


@pytest.mark.asyncio
async def test_slow_subscriber_is_disconnected_without_failing_publish(tmp_path):
    repository = SQLiteRepository(str(tmp_path / "slow-subscriber.db"))
    await repository.initialize()
    events = EventBroker(repository, subscriber_queue_size=1)
    stream = events.subscribe(
        "default",
        "run_slow_subscriber",
        heartbeat_seconds=5,
    )

    first_delivery = asyncio.create_task(stream.__anext__())
    await asyncio.sleep(0)
    first = await events.publish(
        "default",
        RunEvent(
            run_id="run_slow_subscriber",
            type=EventType.RUN_STARTED,
            agent_id="agt_slow_subscriber",
        ),
    )
    assert await first_delivery == first

    second = await events.publish(
        "default",
        RunEvent(
            run_id="run_slow_subscriber",
            type=EventType.AGENT_STARTED,
            agent_id="agt_slow_subscriber",
        ),
    )
    terminal = await events.publish(
        "default",
        RunEvent(
            run_id="run_slow_subscriber",
            type=EventType.RUN_COMPLETED,
            agent_id="agt_slow_subscriber",
        ),
    )

    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()

    persisted = await repository.list_events("default", "run_slow_subscriber")
    assert [event.sequence for event in persisted] == [1, 2, 3]
    assert terminal.sequence == 3

    replayed = [
        event
        async for event in events.subscribe(
            "default",
            "run_slow_subscriber",
            after_sequence=first.sequence,
        )
    ]
    assert replayed == [second, terminal]


@pytest.mark.asyncio
async def test_subscriber_closes_replay_live_registration_window_without_loss(
    tmp_path,
    monkeypatch,
):
    repository = SQLiteRepository(str(tmp_path / "replay-live-window.db"))
    await repository.initialize()
    events = EventBroker(repository)
    snapshot_taken = asyncio.Event()
    release_snapshot = asyncio.Event()
    original_list_events = repository.list_events
    first_list = True

    async def list_events_with_window(tenant_id, run_id, after_sequence=0):
        nonlocal first_list
        snapshot = await original_list_events(
            tenant_id,
            run_id,
            after_sequence,
        )
        if first_list:
            first_list = False
            snapshot_taken.set()
            await release_snapshot.wait()
        return snapshot

    monkeypatch.setattr(repository, "list_events", list_events_with_window)
    stream = events.subscribe(
        "default",
        "run_replay_live_window",
        heartbeat_seconds=5,
    )
    first_delivery = asyncio.create_task(stream.__anext__())
    await snapshot_taken.wait()

    started = await events.publish(
        "default",
        RunEvent(
            run_id="run_replay_live_window",
            type=EventType.RUN_STARTED,
            agent_id="agt_replay_live_window",
        ),
    )
    release_snapshot.set()

    assert await first_delivery == started
    terminal = await events.publish(
        "default",
        RunEvent(
            run_id="run_replay_live_window",
            type=EventType.RUN_COMPLETED,
            agent_id="agt_replay_live_window",
        ),
    )
    assert await stream.__anext__() == terminal
    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()


@pytest.mark.asyncio
async def test_client_metadata_cannot_approve_confirm_tool(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_confirm_tool",
            name="Confirm Tool",
            system_prompt="Use the requested tool.",
            tools=[
                ToolBinding(
                    plugin_id="tool.echo",
                    alias="echo",
                    permission="confirm",
                )
            ],
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=agent.id,
            input='tool:echo {"input": "must not execute"}',
            metadata={"approved_tools": ["echo"]},
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert finished.metrics["approved_tools"] == []
    assert "tool approval required: echo" in finished.error
    assert any(event.type == EventType.PERMISSION_REQUIRED for event in events)
    assert all(event.type != EventType.TOOL_STARTED for event in events)
    assert all(event.type != EventType.TOOL_COMPLETED for event in events)


@pytest.mark.asyncio
async def test_three_level_delegation_with_one_root_slot_does_not_deadlock(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    leaf = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_nested_leaf",
            name="Nested Leaf",
            system_prompt="Return the delegated task.",
            policy=ExecutionPolicy(max_steps=4),
        ),
    )
    middle = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_nested_middle",
            name="Nested Middle",
            system_prompt="Delegate to the leaf.",
            children=[
                ChildMount(
                    alias="leaf",
                    agent_id=leaf.id,
                    max_concurrency=1,
                )
            ],
            policy=ExecutionPolicy(max_steps=6, max_depth=4),
        ),
    )
    root = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_nested_root",
            name="Nested Root",
            system_prompt="Delegate to the middle.",
            children=[
                ChildMount(
                    alias="middle",
                    agent_id=middle.id,
                    max_concurrency=1,
                )
            ],
            policy=ExecutionPolicy(
                max_steps=8,
                max_depth=4,
                max_parallel_children=1,
                timeout_seconds=2,
            ),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=root.id,
            input="delegate:middle delegate:leaf inspect nested concurrency",
        ),
    )
    finished = await asyncio.wait_for(manager.wait("default", run.id), timeout=1)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert "inspect nested concurrency" in finished.output
    assert sum(event.type == EventType.DELEGATION_STARTED for event in events) == 2
    assert sum(event.type == EventType.DELEGATION_COMPLETED for event in events) == 2


@pytest.mark.asyncio
async def test_instance_validates_its_pinned_root_revision_not_invalid_latest(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    root_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_valid_root",
            name="Pinned Valid Root",
            system_prompt="v1 is valid",
        ),
    )
    instance = await repository.save_instance(
        "default",
        AgentInstance(
            id="ins_pinned_valid_root",
            name="Pinned Valid Root Instance",
            agent_id=root_v1.id,
            agent_revision=root_v1.revision,
        ),
    )
    await repository.save_agent(
        "default",
        root_v1.model_copy(
            update={
                "system_prompt": "v2 has a self-cycle",
                "children": [
                    ChildMount(alias="self_cycle", agent_id=root_v1.id),
                ],
            }
        ),
        expected_revision=root_v1.revision,
    )

    run = await manager.start(
        "default",
        RunRequest(instance_id=instance.id, input="inspect the pinned valid root"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.metrics["root_revision"] == root_v1.revision


@pytest.mark.asyncio
async def test_instance_rejects_invalid_pinned_root_even_when_latest_is_valid(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    root_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_invalid_root",
            name="Pinned Invalid Root",
            system_prompt="v1 has a self-cycle",
            children=[
                ChildMount(alias="self_cycle", agent_id="agt_pinned_invalid_root"),
            ],
        ),
    )
    instance = await repository.save_instance(
        "default",
        AgentInstance(
            id="ins_pinned_invalid_root",
            name="Pinned Invalid Root Instance",
            agent_id=root_v1.id,
            agent_revision=root_v1.revision,
        ),
    )
    await repository.save_agent(
        "default",
        root_v1.model_copy(
            update={
                "system_prompt": "v2 removes the cycle",
                "children": [],
            }
        ),
        expected_revision=root_v1.revision,
    )

    with pytest.raises(InvalidTopologyError, match="mounted-agent cycle detected"):
        await manager.start(
            "default",
            RunRequest(instance_id=instance.id, input="must reject the pinned invalid root"),
        )


@pytest.mark.asyncio
async def test_mount_concurrency_semaphores_are_isolated_by_tenant(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    for tenant in ("alpha", "beta"):
        child = await repository.save_agent(
            tenant,
            AgentSpec(
                id="agt_shared_child",
                name="Shared Child",
                system_prompt=f"{tenant} child",
            ),
        )
        parent = await repository.save_agent(
            tenant,
            AgentSpec(
                id="agt_shared_parent",
                name="Shared Parent",
                system_prompt=f"{tenant} parent",
                children=[
                    ChildMount(
                        alias="child",
                        agent_id=child.id,
                        max_concurrency=1,
                    )
                ],
            ),
        )
        run = await manager.start(
            tenant,
            RunRequest(agent_id=parent.id, input=f"delegate:child inspect {tenant}"),
        )
        finished = await manager.wait(tenant, run.id)
        assert finished.status == RunStatus.SUCCEEDED

    alpha_key = ("alpha", "agt_shared_parent", 1, "child")
    beta_key = ("beta", "agt_shared_parent", 1, "child")
    assert alpha_key in manager.runtime._mount_semaphores
    assert beta_key in manager.runtime._mount_semaphores
    assert (
        manager.runtime._mount_semaphores[alpha_key]
        is not manager.runtime._mount_semaphores[beta_key]
    )


@pytest.mark.asyncio
async def test_new_parent_revision_uses_its_updated_mount_concurrency(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_revision_concurrency_child",
            name="Revision Concurrency Child",
            system_prompt="child",
        ),
    )
    parent_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_revision_concurrency_parent",
            name="Revision Concurrency Parent",
            system_prompt="parent v1",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child.id,
                    max_concurrency=1,
                )
            ],
        ),
    )
    run_v1 = await manager.start(
        "default",
        RunRequest(agent_id=parent_v1.id, input="delegate:child run v1"),
    )
    assert (await manager.wait("default", run_v1.id)).status == RunStatus.SUCCEEDED

    parent_v2 = await repository.save_agent(
        "default",
        parent_v1.model_copy(
            update={
                "system_prompt": "parent v2",
                "children": [
                    ChildMount(
                        alias="child",
                        agent_id=child.id,
                        max_concurrency=3,
                    )
                ],
            }
        ),
        expected_revision=parent_v1.revision,
    )
    run_v2 = await manager.start(
        "default",
        RunRequest(agent_id=parent_v2.id, input="delegate:child run v2"),
    )
    assert (await manager.wait("default", run_v2.id)).status == RunStatus.SUCCEEDED

    v1_key = ("default", parent_v1.id, parent_v1.revision, "child")
    v2_key = ("default", parent_v2.id, parent_v2.revision, "child")
    v1_semaphore = manager.runtime._mount_semaphores[v1_key]
    v2_semaphore = manager.runtime._mount_semaphores[v2_key]

    assert v1_semaphore is not v2_semaphore
    assert v1_semaphore._value == 1
    assert v2_semaphore._value == 3


@pytest.mark.asyncio
async def test_instance_override_builds_restricted_effective_spec_and_runtime_context(
    tmp_path,
    monkeypatch,
):
    repository, manager = await make_runtime(tmp_path)
    definition = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_instance_override_context",
            name="Instance Override Context",
            system_prompt="Use the echo tool when requested.",
            tools=[ToolBinding(plugin_id="tool.echo", alias="echo")],
            policy=ExecutionPolicy(
                max_steps=8,
                max_depth=4,
                max_tool_calls=10,
                max_parallel_children=5,
                timeout_seconds=30,
                token_budget=1_000,
                fail_fast=False,
            ),
        ),
    )
    immutable_revision = definition.model_dump_json()
    instance = await repository.save_instance(
        "default",
        AgentInstance(
            id="ins_instance_override_context",
            name="Instance Override Context",
            agent_id=definition.id,
            agent_revision=definition.revision,
            environment="test-sandbox",
            config_overrides={
                "policy": {
                    "max_steps": 3,
                    "max_depth": 8,
                    "max_tool_calls": 20,
                    "max_parallel_children": 2,
                    "timeout_seconds": 60,
                    "token_budget": 500,
                    "fail_fast": True,
                }
            },
        ),
    )

    provider_metadata = []
    middleware_context = {}
    tool_context = {}
    registry = manager.runtime.registry
    original_create_provider = registry.create_provider

    class CapturingProvider:
        def __init__(self, provider):
            self.provider = provider

        async def complete(self, request):
            provider_metadata.append(dict(request.metadata))
            return await self.provider.complete(request)

    class CapturingMiddleware:
        async def before_model(self, context, request):
            middleware_context.update(context)
            return request

        async def after_model(self, context, output):
            return output

        async def before_tool(self, context, name, arguments):
            return arguments

        async def after_tool(self, context, name, result):
            return result

    class CapturingTool:
        name = "echo"
        description = "Capture the runtime context."
        parameters = {
            "type": "object",
            "properties": {"input": {}},
            "required": ["input"],
            "additionalProperties": False,
        }

        def definition(self, exposed_name=None):
            return {
                "type": "function",
                "function": {
                    "name": exposed_name or self.name,
                    "description": self.description,
                    "parameters": self.parameters,
                },
            }

        async def invoke(self, arguments, context):
            tool_context.update(context)
            return {"input": arguments.get("input")}

    monkeypatch.setattr(
        registry,
        "create_provider",
        lambda binding: CapturingProvider(original_create_provider(binding)),
    )
    monkeypatch.setattr(
        registry,
        "create_middlewares",
        lambda bindings: [CapturingMiddleware()],
    )
    monkeypatch.setattr(registry, "create_tool", lambda binding: CapturingTool())

    run = await manager.start(
        "default",
        RunRequest(
            instance_id=instance.id,
            input='tool:echo {"input": "inspect context"}',
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)
    started = next(event for event in events if event.type == EventType.RUN_STARTED)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.metrics["instance_id"] == instance.id
    assert finished.metrics["environment"] == "test-sandbox"
    assert finished.metrics["effective_policy"] == {
        "max_steps": 3,
        "max_depth": 4,
        "max_tool_calls": 10,
        "max_parallel_children": 2,
        "timeout_seconds": 30.0,
        "token_budget": 500,
        "fail_fast": True,
    }
    assert started.payload["instance_id"] == instance.id
    assert started.payload["environment"] == "test-sandbox"
    for context in (provider_metadata[0], middleware_context, tool_context):
        assert context["instance_id"] == instance.id
        assert context["environment"] == "test-sandbox"
    assert (
        await repository.get_agent("default", definition.id, definition.revision)
    ).model_dump_json() == immutable_revision


@pytest.mark.asyncio
async def test_instance_step_override_actually_tightens_shared_run_budget(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_instance_override_child",
            name="Instance Override Child",
            system_prompt="Return the delegated input.",
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_instance_override_parent",
            name="Instance Override Parent",
            system_prompt="Delegate the task.",
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=ExecutionPolicy(max_steps=8, max_depth=4),
        ),
    )
    instance = await repository.save_instance(
        "default",
        AgentInstance(
            id="ins_instance_override_budget",
            name="Instance Override Budget",
            agent_id=parent.id,
            agent_revision=parent.revision,
            config_overrides={"policy": {"max_steps": 1}},
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            instance_id=instance.id,
            input="delegate:child consume the effective shared budget",
        ),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.FAILED
    assert finished.metrics["effective_policy"]["max_steps"] == 1
    assert "step budget exhausted" in finished.error


@pytest.mark.asyncio
async def test_direct_agent_run_keeps_empty_instance_context(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_direct_context",
            name="Direct Context",
            system_prompt="Return the input.",
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="run without an Instance"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)
    started = next(event for event in events if event.type == EventType.RUN_STARTED)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.metrics["instance_id"] is None
    assert finished.metrics["environment"] is None
    assert started.payload["instance_id"] is None
    assert started.payload["environment"] is None
