import pytest

from uai_forge.builtins import register_builtins
from uai_forge.models import AgentInstance, ModelBinding, PluginKind, PluginManifest, ToolBinding
from uai_forge.registry import PluginCompatibilityError, PluginRegistry


def test_builtin_capability_catalog_covers_extension_points():
    registry = PluginRegistry()
    register_builtins(registry)

    kinds = {manifest.kind for manifest in registry.manifests()}
    assert {
        PluginKind.PROVIDER,
        PluginKind.TOOL,
        PluginKind.MEMORY,
        PluginKind.STORAGE,
        PluginKind.EVENT_BUS,
        PluginKind.SCHEDULER,
        PluginKind.MIDDLEWARE,
        PluginKind.UI,
    }.issubset(kinds)


def test_incompatible_plugin_protocol_fails_closed():
    registry = PluginRegistry()
    manifest = PluginManifest(
        id="storage.future",
        kind=PluginKind.STORAGE,
        display_name="Future storage",
        protocol_version="2.0",
    )

    with pytest.raises(PluginCompatibilityError):
        registry.register_manifest(manifest)


def test_binding_configs_reject_plaintext_credentials_and_accept_references():
    with pytest.raises(ValueError, match="inline credential"):
        ModelBinding(config={"api_key": "sk-plaintext"})

    with pytest.raises(ValueError, match="inline credential"):
        ToolBinding(
            plugin_id="tool.remote",
            config={"headers": {"Authorization": "Bearer plaintext"}},
        )

    with pytest.raises(ValueError, match="inline credential"):
        AgentInstance(
            name="Unsafe Instance",
            agent_id="agt_target",
            config_overrides={"provider": {"password": "plaintext"}},
        )

    safe = ModelBinding(
        provider="openai_compatible",
        model="example",
        config={"api_key_env": "OPENAI_API_KEY"},
    )
    assert safe.config["api_key_env"] == "OPENAI_API_KEY"
