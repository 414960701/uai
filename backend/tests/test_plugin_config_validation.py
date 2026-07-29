from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.models import (
    AgentSpec,
    MemoryBinding,
    MiddlewareBinding,
    ModelBinding,
    PluginKind,
    PluginManifest,
    RunRecord,
    RunRequest,
    ToolBinding,
)
from uai_forge.registry import PluginBindingError, PluginRegistry
from uai_forge.run_manager import RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.settings import Settings
from uai_forge.storage import SQLiteRepository


def make_registry() -> PluginRegistry:
    registry = PluginRegistry()
    register_builtins(registry)
    return registry


@pytest.mark.parametrize(
    ("spec", "plugin_id", "kind", "keyword"),
    [
        (
            AgentSpec(
                name="Invalid Provider",
                system_prompt="provider config",
                model=ModelBinding(
                    provider="mock",
                    config={"unknown": True},
                ),
            ),
            "mock",
            PluginKind.PROVIDER,
            "additionalProperties",
        ),
        (
            AgentSpec(
                name="Invalid Tool",
                system_prompt="tool config",
                tools=[
                    ToolBinding(
                        plugin_id="tool.calculator",
                        config={"unknown": True},
                    )
                ],
            ),
            "tool.calculator",
            PluginKind.TOOL,
            "additionalProperties",
        ),
        (
            AgentSpec(
                name="Invalid Memory",
                system_prompt="memory config",
                memory=MemoryBinding(config={"max_messages": 1}),
            ),
            "memory.in_process",
            PluginKind.MEMORY,
            "minimum",
        ),
        (
            AgentSpec(
                name="Invalid Middleware",
                system_prompt="middleware config",
                middlewares=[
                    MiddlewareBinding(
                        plugin_id="middleware.audit_tags",
                        config={"tags": {"invalid": 42}},
                    )
                ],
            ),
            "middleware.audit_tags",
            PluginKind.MIDDLEWARE,
            "type",
        ),
    ],
)
def test_every_runtime_binding_kind_uses_its_manifest_schema(
    spec,
    plugin_id,
    kind,
    keyword,
):
    registry = make_registry()

    with pytest.raises(PluginBindingError) as raised:
        registry.validate_agent_spec(spec)

    assert raised.value.as_detail() == {
        "code": "plugin.config_invalid",
        "plugin_id": plugin_id,
        "expected_kind": kind.value,
        "path": (
            "/tags/invalid"
            if plugin_id == "middleware.audit_tags"
            else "/max_messages"
            if plugin_id == "memory.in_process"
            else "/"
        ),
        "keyword": keyword,
    }


def test_third_party_schema_is_compiled_and_enforced():
    registry = make_registry()
    manifest = PluginManifest(
        id="tool.third_party",
        kind=PluginKind.TOOL,
        display_name="Third-party test tool",
        source="entry_point",
        config_schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["safe"]},
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    )
    registry.register_tool(manifest, lambda binding: object())

    resolved = registry.validate_binding(
        "tool.third_party",
        PluginKind.TOOL,
        {"mode": "safe"},
    )
    assert resolved is manifest

    with pytest.raises(PluginBindingError) as raised:
        registry.validate_binding(
            "tool.third_party",
            PluginKind.TOOL,
            {"mode": "unsafe"},
        )
    assert raised.value.code == "plugin.config_invalid"
    assert raised.value.keyword == "enum"
    assert "unsafe" not in str(raised.value)


def test_invalid_plugin_schema_unknown_plugin_and_kind_mismatch_are_stable():
    registry = make_registry()
    invalid_schema = PluginManifest(
        id="tool.invalid_schema",
        kind=PluginKind.TOOL,
        display_name="Invalid schema",
        config_schema={"type": "not-a-json-schema-type"},
    )

    with pytest.raises(PluginBindingError) as invalid:
        registry.register_tool(invalid_schema, lambda binding: object())
    assert invalid.value.code == "plugin.schema_invalid"
    assert invalid.value.plugin_id == "tool.invalid_schema"

    with pytest.raises(PluginBindingError) as unknown:
        registry.validate_binding("tool.missing", PluginKind.TOOL, {})
    assert unknown.value.as_detail()["code"] == "plugin.not_found"

    with pytest.raises(PluginBindingError) as mismatch:
        registry.validate_binding("mock", PluginKind.TOOL, {})
    assert mismatch.value.as_detail() == {
        "code": "plugin.kind_mismatch",
        "plugin_id": "mock",
        "expected_kind": "tool",
        "path": "/",
        "registered_kinds": ["provider"],
    }

    with pytest.raises(PluginBindingError) as registration_mismatch:
        registry.register_tool(
            PluginManifest(
                id="provider.wrong_registration_method",
                kind=PluginKind.PROVIDER,
                display_name="Wrong registration method",
            ),
            lambda binding: object(),
        )
    assert registration_mismatch.value.code == "plugin.kind_mismatch"

    registry.register_manifest(
        PluginManifest(
            id="tool.missing_factory",
            kind=PluginKind.TOOL,
            display_name="Missing factory",
        )
    )
    with pytest.raises(PluginBindingError) as missing_factory:
        registry.validate_binding(
            "tool.missing_factory",
            PluginKind.TOOL,
            {},
        )
    assert missing_factory.value.code == "plugin.factory_missing"


def test_save_boundary_rejects_calculator_unknown_config_without_persisting(
    tmp_path: Path,
):
    app = create_app(
        Settings(
            database_path=str(tmp_path / "save-boundary.db"),
            allowed_origins=["http://localhost:3000"],
            seed_demo=False,
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_invalid_calculator_config",
                "name": "Invalid Calculator",
                "system_prompt": "This revision must not be saved.",
                "tools": [
                    {
                        "plugin_id": "tool.calculator",
                        "config": {"unexpected": True},
                    }
                ],
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == {
            "code": "plugin.config_invalid",
            "plugin_id": "tool.calculator",
            "expected_kind": "tool",
            "path": "/",
            "keyword": "additionalProperties",
        }
        assert (
            client.get("/api/v1/agents/agt_invalid_calculator_config").status_code
            == 404
        )

        valid = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_calculator_patch_target",
                "name": "Calculator Patch Target",
                "system_prompt": "Start with a valid calculator binding.",
                "tools": [{"plugin_id": "tool.calculator"}],
            },
        )
        assert valid.status_code == 201
        rejected_patch = client.patch(
            "/api/v1/agents/agt_calculator_patch_target",
            json={
                "expected_revision": valid.json()["revision"],
                "tools": [
                    {
                        "plugin_id": "tool.calculator",
                        "config": {"unexpected": True},
                    }
                ],
            },
        )
        assert rejected_patch.status_code == 422
        unchanged = client.get(
            "/api/v1/agents/agt_calculator_patch_target"
        ).json()
        assert unchanged["revision"] == valid.json()["revision"]
        assert unchanged["tools"][0]["config"] == {}


@pytest.mark.parametrize(
    ("plugin_id", "code"),
    [
        ("tool.missing", "plugin.not_found"),
        ("mock", "plugin.kind_mismatch"),
    ],
)
def test_api_returns_stable_unknown_and_kind_mismatch_errors(
    tmp_path: Path,
    plugin_id,
    code,
):
    app = create_app(
        Settings(
            database_path=str(tmp_path / f"{code}.db"),
            allowed_origins=["http://localhost:3000"],
            seed_demo=False,
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents",
            json={
                "id": f"agt_{code.replace('.', '_')}",
                "name": "Invalid Plugin Reference",
                "system_prompt": "Reject before persistence.",
                "tools": [{"plugin_id": plugin_id}],
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == code
        assert response.json()["detail"]["plugin_id"] == plugin_id
        assert response.json()["detail"]["expected_kind"] == "tool"


def test_save_boundary_uses_dynamically_registered_plugin_schema(tmp_path: Path):
    app = create_app(
        Settings(
            database_path=str(tmp_path / "dynamic-plugin.db"),
            allowed_origins=["http://localhost:3000"],
            seed_demo=False,
        )
    )
    app.state.container.registry.register_tool(
        PluginManifest(
            id="tool.dynamic_schema",
            kind=PluginKind.TOOL,
            display_name="Dynamic schema",
            source="entry_point",
            config_schema={
                "type": "object",
                "properties": {"enabled_feature": {"type": "boolean"}},
                "required": ["enabled_feature"],
                "additionalProperties": False,
            },
        ),
        lambda binding: object(),
    )
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_dynamic_schema_valid",
                "name": "Dynamic Schema Valid",
                "system_prompt": "Use a dynamically registered schema.",
                "tools": [
                    {
                        "plugin_id": "tool.dynamic_schema",
                        "config": {"enabled_feature": True},
                    }
                ],
            },
        )
        assert accepted.status_code == 201

        rejected = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_dynamic_schema_invalid",
                "name": "Dynamic Schema Invalid",
                "system_prompt": "This revision must be rejected.",
                "tools": [
                    {
                        "plugin_id": "tool.dynamic_schema",
                        "config": {"enabled_feature": "yes"},
                    }
                ],
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["code"] == "plugin.config_invalid"
        assert rejected.json()["detail"]["keyword"] == "type"


@pytest.mark.asyncio
async def test_run_submission_and_runtime_revalidate_bypassed_storage(tmp_path: Path):
    repository = SQLiteRepository(str(tmp_path / "bypassed-storage.db"))
    await repository.initialize()
    registry = make_registry()
    events = EventBroker(repository)
    runtime = AgentRuntime(repository, registry, events)
    manager = RunManager(
        repository,
        runtime,
        events,
        AgentGraphValidator(repository),
    )
    invalid = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_bypassed_validation",
            name="Bypassed Validation",
            system_prompt="Raw storage accepted an old invalid revision.",
            tools=[
                ToolBinding(
                    plugin_id="tool.calculator",
                    config={"unexpected": True},
                )
            ],
        ),
    )

    with pytest.raises(PluginBindingError) as submission:
        await manager.start(
            "default",
            RunRequest(agent_id=invalid.id, input="must fail before persistence"),
        )
    assert submission.value.code == "plugin.config_invalid"
    assert await repository.list_runs("default") == []

    direct_run = RunRecord(
        tenant_id="default",
        agent_id=invalid.id,
        session_id="ses_direct_runtime_bypass",
        input="direct runtime bypass",
    )
    with pytest.raises(PluginBindingError) as execution:
        await runtime.execute(direct_run, invalid)
    assert execution.value.code == "plugin.config_invalid"
    assert await repository.list_events("default", direct_run.id) == []
