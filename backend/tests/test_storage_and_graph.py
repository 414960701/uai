from pathlib import Path

import pytest

from uai_forge.graph import AgentGraphValidator
from uai_forge.models import AgentSpec, ChildMount, ModelBinding
from uai_forge.storage import RevisionConflictError, SQLiteRepository


@pytest.fixture
async def repository(tmp_path: Path):
    repo = SQLiteRepository(str(tmp_path / "test.db"))
    await repo.initialize()
    return repo


@pytest.mark.asyncio
async def test_agent_updates_are_versioned_and_optimistic(repository):
    created = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_versioned",
            name="Versioned Agent",
            system_prompt="v1",
            model=ModelBinding(),
        ),
    )
    updated = await repository.save_agent(
        "default",
        created.model_copy(update={"system_prompt": "v2"}),
        expected_revision=1,
    )

    assert updated.revision == 2
    assert (await repository.get_agent("default", created.id, 1)).system_prompt == "v1"
    assert (await repository.get_agent("default", created.id, 2)).system_prompt == "v2"
    with pytest.raises(RevisionConflictError):
        await repository.save_agent(
            "default",
            updated.model_copy(update={"system_prompt": "stale"}),
            expected_revision=1,
        )


@pytest.mark.asyncio
async def test_latest_pointer_can_roll_back_without_reusing_revision(repository):
    v1 = await repository.save_agent(
        "default",
        AgentSpec(id="agt_rollback", name="Rollback Agent", system_prompt="v1"),
    )
    v2 = await repository.save_agent(
        "default",
        v1.model_copy(update={"system_prompt": "v2"}),
        expected_revision=v1.revision,
    )
    v3 = await repository.save_agent(
        "default",
        v2.model_copy(update={"system_prompt": "v3"}),
        expected_revision=v2.revision,
    )

    latest = await repository.rollback_agent(
        "default", v1.id, v1.revision, expected_revision=v3.revision
    )
    assert latest.revision == v1.revision
    assert (await repository.get_agent("default", v1.id)).system_prompt == "v1"
    assert [item.revision for item in await repository.list_agent_revisions("default", v1.id)] == [3, 2, 1]

    v4 = await repository.save_agent(
        "default",
        latest.model_copy(update={"system_prompt": "v4 after rollback"}),
        expected_revision=v1.revision,
    )
    assert v4.revision == 4
    assert (await repository.get_agent("default", v1.id)).system_prompt == "v4 after rollback"


@pytest.mark.asyncio
async def test_mount_cycles_are_rejected(repository):
    agent_a = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_cycle_a",
            name="Cycle A",
            system_prompt="A",
            children=[ChildMount(alias="to_b", agent_id="agt_cycle_b")],
        ),
    )
    await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_cycle_b",
            name="Cycle B",
            system_prompt="B",
            children=[ChildMount(alias="to_a", agent_id=agent_a.id)],
        ),
    )

    result = await AgentGraphValidator(repository).validate("default", agent_a.id)

    assert result.valid is False
    assert any(issue.code == "mount_cycle" for issue in result.issues)
    assert len(result.edges) == 2


@pytest.mark.asyncio
async def test_graph_traverses_the_pinned_revision_instead_of_latest(repository):
    child_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_child",
            name="Pinned Child",
            system_prompt="v1 has no outgoing mounts",
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_parent",
            name="Pinned Parent",
            system_prompt="parent",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child_v1.id,
                    revision=child_v1.revision,
                )
            ],
        ),
    )
    await repository.save_agent(
        "default",
        child_v1.model_copy(
            update={
                "system_prompt": "v2 would introduce a cycle",
                "children": [
                    ChildMount(alias="back_to_parent", agent_id=parent.id),
                ],
            }
        ),
        expected_revision=child_v1.revision,
    )

    result = await AgentGraphValidator(repository).validate("default", parent.id)

    assert result.valid is True
    assert not any(issue.code == "mount_cycle" for issue in result.issues)


@pytest.mark.asyncio
async def test_graph_unpinned_mount_follows_latest_pointer(repository):
    child_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_unpinned_child",
            name="Unpinned Child",
            system_prompt="v1 has no outgoing mounts",
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_unpinned_parent",
            name="Unpinned Parent",
            system_prompt="parent",
            children=[ChildMount(alias="child", agent_id=child_v1.id)],
        ),
    )
    child_v2 = await repository.save_agent(
        "default",
        child_v1.model_copy(
            update={
                "system_prompt": "v2 introduces a cycle",
                "children": [ChildMount(alias="back", agent_id=parent.id)],
            }
        ),
        expected_revision=child_v1.revision,
    )

    latest_v2 = await AgentGraphValidator(repository).validate("default", parent.id)
    assert latest_v2.valid is False
    assert any(issue.code == "mount_cycle" for issue in latest_v2.issues)

    await repository.rollback_agent(
        "default", child_v1.id, child_v1.revision, expected_revision=child_v2.revision
    )
    rolled_back = await AgentGraphValidator(repository).validate("default", parent.id)
    assert rolled_back.valid is True


@pytest.mark.asyncio
async def test_graph_detects_a_cycle_present_only_in_the_pinned_revision(repository):
    child_v1 = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_cycle_child",
            name="Pinned Cycle Child",
            system_prompt="v1 points back to the future parent",
            children=[
                ChildMount(alias="back_to_parent", agent_id="agt_pinned_cycle_parent"),
            ],
        ),
    )
    parent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_pinned_cycle_parent",
            name="Pinned Cycle Parent",
            system_prompt="parent",
            children=[
                ChildMount(
                    alias="child",
                    agent_id=child_v1.id,
                    revision=child_v1.revision,
                )
            ],
        ),
    )
    await repository.save_agent(
        "default",
        child_v1.model_copy(
            update={
                "system_prompt": "v2 removes the cycle",
                "children": [],
            }
        ),
        expected_revision=child_v1.revision,
    )

    result = await AgentGraphValidator(repository).validate("default", parent.id)

    assert result.valid is False
    assert any(issue.code == "mount_cycle" for issue in result.issues)


@pytest.mark.asyncio
async def test_tenant_data_is_isolated(repository):
    await repository.save_agent(
        "alpha",
        AgentSpec(id="agt_shared_name", name="Alpha Agent", system_prompt="alpha"),
    )
    assert await repository.get_agent("beta", "agt_shared_name") is None
    assert len(await repository.list_agents("alpha")) == 1
    assert await repository.list_agents("beta") == []
