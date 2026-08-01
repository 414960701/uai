from uai_forge.models import (
    ChildMount,
    ExecutionPolicy,
    DEFAULT_AGENT_TOOL_PLUGIN_IDS,
    default_tool_bindings,
)


def test_new_agent_defaults_are_usable_for_remote_multistep_work():
    assert [binding.plugin_id for binding in default_tool_bindings()] == list(
        DEFAULT_AGENT_TOOL_PLUGIN_IDS
    )
    assert all(binding.permission == "auto" for binding in default_tool_bindings())
    assert ExecutionPolicy().model_dump(exclude={"fail_fast"}) == {
        "max_steps": 20,
        "max_depth": 6,
        "max_tool_calls": 64,
        "max_parallel_children": 6,
        "timeout_seconds": 300.0,
        "token_budget": 64_000,
    }
    assert ChildMount(
        alias="researcher",
        agent_id="agt_researcher",
    ).max_concurrency == 4
