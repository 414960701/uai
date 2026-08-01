import asyncio
from pathlib import Path

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.models import (
    AgentSpec,
    ChildMount,
    EventType,
    ExecutionMode,
    ExecutionPolicy,
    PlanEditRequest,
    PlanStep,
    RunEvent,
    RunRequest,
    RunStatus,
    ThinkingMode,
    ToolBinding,
)
from uai_forge.registry import PluginRegistry
from uai_forge.run_manager import InvalidTopologyError, RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.storage import SQLiteRepository
from uai_forge.ports import TokenUsage
from test_support import register_test_provider


async def make_runtime(tmp_path: Path, *, streaming: bool = False):
    repository = SQLiteRepository(str(tmp_path / "runtime.db"))
    await repository.initialize()
    registry = PluginRegistry()
    register_builtins(registry)
    register_test_provider(registry, streaming=streaming)
    register_test_provider(registry, "openai_compatible")
    events = EventBroker(repository)
    validator = AgentGraphValidator(repository)
    runtime = AgentRuntime(repository, registry, events)
    manager = RunManager(repository, runtime, events, validator)
    return repository, manager


@pytest.mark.asyncio
async def test_streaming_model_publishes_deltas_and_trace_chain(tmp_path):
    repository, manager = await make_runtime(tmp_path, streaming=True)
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_streaming_trace",
            name="Streaming Trace Agent",
            system_prompt="Answer clearly.",
            policy=ExecutionPolicy(max_steps=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="stream this response"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert "stream this response" in finished.output
    assert [event.type for event in events].count(EventType.MODEL_DELTA) == 2
    assert any(event.type == EventType.AGENT_PROGRESS for event in events)
    assert events[0].trace_id == f"trace_{run.id}"
    assert events[0].span_id
    assert all(event.trace_id == events[0].trace_id for event in events)
    assert all(event.span_id for event in events)
    assert events[-1].type == EventType.RUN_COMPLETED


def test_stream_usage_merge_preserves_partial_cache_dimensions():
    merged = AgentRuntime._merge_usage(
        TokenUsage(input_tokens=11, cached_input_tokens=8),
        TokenUsage(output_tokens=5, cache_creation_input_tokens=1),
    )

    assert merged.input_tokens == 11
    assert merged.output_tokens == 5
    assert merged.cached_input_tokens == 8
    assert merged.cache_creation_input_tokens == 1
    assert merged.total_tokens == 16


@pytest.mark.asyncio
async def test_weather_missing_location_fast_path_skips_model_and_child_calls(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_fast_weather_child",
            name="天气子 Agent",
            description="查询天气",
            system_prompt="查询天气。",
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_fast_weather_parent",
            name="天气路由 Agent",
            system_prompt="将天气请求交给合适的 Agent。",
            children=[ChildMount(alias="weather", agent_id=child.id)],
            labels={"routing.fast_path": "weather_missing_location"},
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="今天天气怎么样"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.metrics["fast_path"] == "weather_missing_location"
    assert "城市或地区" in finished.output
    assert not any(event.type == EventType.MODEL_STARTED for event in events)
    assert not any(event.type == EventType.DELEGATION_STARTED for event in events)
    assert not any(event.type == EventType.AGENT_STARTED and event.agent_id == child.id for event in events)
    assert any(
        event.type == EventType.AGENT_PROGRESS
        and event.payload.get("phase") == "preflight"
        for event in events
    )
    agent_completed = next(event for event in events if event.type == EventType.AGENT_COMPLETED)
    assert agent_completed.payload["duration_ms"] >= 0
    assert events[-1].type == EventType.RUN_COMPLETED


@pytest.mark.asyncio
async def test_trace_events_include_operation_durations(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_duration_child",
            name="Duration Child",
            system_prompt="Return the delegated task.",
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_duration_parent",
            name="Duration Parent",
            system_prompt="Delegate when requested.",
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=ExecutionPolicy(max_steps=8, max_depth=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=parent.id, input="delegate:child measure this trace"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    for event_type in (
        EventType.MODEL_COMPLETED,
        EventType.DELEGATION_COMPLETED,
        EventType.AGENT_COMPLETED,
    ):
        matching = [event for event in events if event.type == event_type]
        assert matching
        assert all(event.payload["duration_ms"] >= 0 for event in matching)
    model_steps = {
        event.payload["step"]
        for event in events
        if event.type == EventType.MODEL_STARTED
    }
    assert model_steps
    assert all(
        event.payload["step"] in model_steps
        for event in events
        if event.type == EventType.MODEL_COMPLETED
    )


@pytest.mark.asyncio
async def test_thinking_mode_is_carried_into_run_metrics_and_public_resolution(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_thinking_preference",
            name="Thinking Preference Agent",
            system_prompt="Answer clearly.",
            policy=ExecutionPolicy(max_steps=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=agent.id,
            input="use the selected thinking preference",
            thinking_mode=ThinkingMode.ON,
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.metrics["thinking_mode"] == "on"
    model_started = next(event for event in events if event.type == EventType.MODEL_STARTED)
    assert model_started.payload["thinking_mode"] == "on"
    assert model_started.payload["thinking_resolution"] == "unsupported"
    assert any(
        event.payload.get("phase") == "thinking_mode"
        and event.payload.get("status") == "degraded"
        for event in events
    )


@pytest.mark.asyncio
async def test_plan_mode_blocks_tools_and_child_delegation(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    child = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_plan_child",
            name="Plan Child",
            system_prompt="Return the delegated task.",
            policy=ExecutionPolicy(max_steps=3),
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_plan_parent",
            name="Plan Parent",
            system_prompt="Plan the requested work.",
            tools=[ToolBinding(plugin_id="tool.echo", alias="echo")],
            children=[ChildMount(alias="child", agent_id=child.id)],
            policy=ExecutionPolicy(max_steps=3, max_depth=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(
            agent_id=parent.id,
            input='tool:echo {"input":"must remain a plan"} delegate:child do not run',
            execution_mode=ExecutionMode.PLAN,
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.metrics["execution_mode"] == "plan"
    assert not any(event.type == EventType.TOOL_STARTED for event in events)
    assert not any(event.type == EventType.DELEGATION_STARTED for event in events)
    started = next(event for event in events if event.type == EventType.RUN_STARTED)
    assert started.payload["execution_mode"] == "plan"
    model_started = next(event for event in events if event.type == EventType.MODEL_STARTED)
    assert model_started.payload["execution_mode"] == "plan"
    assert any(
        event.type == EventType.AGENT_PROGRESS
        and event.payload.get("phase") == "plan"
        and "不调用工具或子 Agent" in event.payload.get("message", "")
        for event in events
    )


@pytest.mark.asyncio
async def test_plan_mode_creates_reviewable_plan_and_approval_starts_pinned_execution(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_plan_review_flow",
            name="Plan Review Agent",
            system_prompt="Produce a clear implementation plan.",
            policy=ExecutionPolicy(max_steps=3),
        ),
    )

    plan_run = await manager.start(
        "default",
        RunRequest(
            agent_id=agent.id,
            input="整理一个可审阅的发布流程",
            execution_mode=ExecutionMode.PLAN,
        ),
    )
    finished_plan = await manager.wait("default", plan_run.id)
    assert finished_plan is not None
    assert finished_plan.plan is not None
    assert finished_plan.plan.plan_id.startswith("plan_")
    assert finished_plan.plan.status.value == "proposed"
    assert finished_plan.plan.steps
    assert finished_plan.metrics["plan_id"] == finished_plan.plan.plan_id

    edited = await manager.edit_plan(
        "default",
        plan_run.id,
        PlanEditRequest(
            expected_version=finished_plan.plan.version,
            title="发布流程（已审阅）",
            goal="按批准后的步骤完成发布准备",
            assumptions=["当前环境为本地测试环境"],
            steps=[
                PlanStep(
                    id="step_01",
                    title="检查配置",
                    description="检查模型和运行配置",
                    risk="low",
                ),
                PlanStep(
                    id="step_02",
                    title="执行验证",
                    description="运行回归验证并记录结果",
                    risk="medium",
                ),
            ],
            risks=["发布前需要再次确认外部副作用边界"],
        ),
    )
    assert edited.version == 2
    assert edited.status.value == "needs_revision"

    execution = await manager.approve_plan("default", plan_run.id, edited.version)
    assert execution.id != plan_run.id
    assert execution.metrics["execution_mode"] == "execute"
    assert execution.metrics["source_plan_id"] == edited.plan_id
    assert execution.metrics["source_plan_run_id"] == plan_run.id
    assert execution.metrics["root_revision"] == agent.revision

    finished_execution = await manager.wait("default", execution.id)
    assert finished_execution is not None
    assert finished_execution.status == RunStatus.SUCCEEDED
    source_after = await repository.get_run("default", plan_run.id)
    assert source_after is not None and source_after.plan is not None
    assert source_after.plan.status.value == "completed"
    assert all(step.status.value == "completed" for step in source_after.plan.steps)

    plan_events = await repository.list_events("default", plan_run.id)
    assert [event.type for event in plan_events].count(EventType.PLAN_PROPOSED) == 1
    assert [event.type for event in plan_events].count(EventType.PLAN_UPDATED) == 1
    assert [event.type for event in plan_events].count(EventType.PLAN_APPROVED) == 1
    assert [event.type for event in plan_events].count(EventType.PLAN_EXECUTION_STARTED) == 1
    assert [event.type for event in plan_events].count(EventType.PLAN_COMPLETED) == 1


@pytest.mark.asyncio
async def test_streaming_model_emits_deltas_after_tool_calls_are_completed(tmp_path):
    repository, manager = await make_runtime(tmp_path, streaming=True)
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_streaming_tools",
            name="Streaming Tool Agent",
            system_prompt="Use tools when requested.",
            tools=[ToolBinding(plugin_id="tool.echo", alias="echo")],
            policy=ExecutionPolicy(max_steps=3),
        ),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input='tool:echo {"input":"safe"}'),
    )
    await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)

    deltas = [event for event in events if event.type == EventType.MODEL_DELTA]
    assert len(deltas) == 2
    assert all("tool_calls" not in event.payload for event in deltas)
    assert "已完成协作" in "".join(event.payload["text"] for event in deltas)
    assert any(event.type == EventType.TOOL_STARTED for event in events)


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
async def test_run_can_pin_agent_revision_not_invalid_latest(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    root_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_valid_root",
            name="Pinned Valid Root",
            system_prompt="v1 is valid",
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
        RunRequest(
            agent_id=root_v1.id,
            agent_revision=root_v1.revision,
            input="inspect the pinned valid root",
        ),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.agent_revision == root_v1.revision
    assert finished.metrics["root_revision"] == root_v1.revision


@pytest.mark.asyncio
async def test_run_rejects_invalid_pinned_revision_even_when_latest_is_valid(tmp_path):
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
            RunRequest(
                agent_id=root_v1.id,
                agent_revision=root_v1.revision,
                input="must reject the pinned invalid root",
            ),
        )


@pytest.mark.asyncio
async def test_run_uses_latest_agent_revision_by_default(tmp_path):
    repository, manager = await make_runtime(tmp_path)
    v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_latest_default",
            name="Latest Default",
            system_prompt="v1",
        ),
    )
    v2 = await repository.save_agent(
        "default",
        v1.model_copy(update={"system_prompt": "v2"}),
        expected_revision=v1.revision,
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=v1.id, input="use the latest revision"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.agent_revision == v2.revision
    assert finished.metrics["root_revision"] == v2.revision


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
async def test_agent_revision_context_is_server_derived(
    tmp_path,
    monkeypatch,
):
    repository, manager = await make_runtime(tmp_path)
    definition = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_revision_context",
            name="Revision Context",
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
            agent_id=definition.id,
            agent_revision=definition.revision,
            input='tool:echo {"input": "inspect context"}',
        ),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)
    started = next(event for event in events if event.type == EventType.RUN_STARTED)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.agent_revision == definition.revision
    assert finished.metrics["effective_policy"] == {
        "max_steps": 8,
        "max_depth": 4,
        "max_tool_calls": 10,
        "max_parallel_children": 5,
        "timeout_seconds": 30.0,
        "token_budget": 1_000,
        "fail_fast": False,
    }
    assert started.payload["agent_revision"] == definition.revision
    for context in (provider_metadata[0], middleware_context, tool_context):
        assert context["agent_revision"] == definition.revision
    assert (
        await repository.get_agent("default", definition.id, definition.revision)
    ).model_dump_json() == immutable_revision


@pytest.mark.asyncio
async def test_direct_agent_run_uses_agent_revision_context(tmp_path):
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
        RunRequest(agent_id=agent.id, input="run the current Agent"),
    )
    finished = await manager.wait("default", run.id)
    events = await repository.list_events("default", run.id)
    started = next(event for event in events if event.type == EventType.RUN_STARTED)

    assert finished.status == RunStatus.SUCCEEDED
    assert finished.agent_revision == agent.revision
    assert started.payload["agent_revision"] == agent.revision
