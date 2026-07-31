import pytest

from uai_forge.builtins import register_builtins
from uai_forge.models import AgentInstance, ModelBinding, PluginKind, PluginManifest, ToolBinding
from uai_forge.registry import PluginBindingError, PluginCompatibilityError, PluginRegistry


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


def test_builtin_provider_catalog_excludes_test_adapters():
    registry = PluginRegistry()
    register_builtins(registry)

    providers = registry.manifests(PluginKind.PROVIDER)
    assert [manifest.id for manifest in providers] == [
        "anthropic_messages",
        "openai_compatible",
    ]
    assert all("test" not in manifest.id for manifest in providers)
    assert any(item.id == "deepseek-r1" for item in providers[1].model_catalog)
    assert any(item.id == "qwen3.8-max-preview" for item in providers[1].model_catalog)
    assert any(item.id == "kimi-k2.7-code" for item in providers[1].model_catalog)
    assert any(item.id == "glm-5-turbo" for item in providers[1].model_catalog)
    assert any(item.id == "doubao-seed-2-1-pro" for item in providers[1].model_catalog)
    assert any(item.id == "MiniMax-M3" for item in providers[1].model_catalog)
    assert any(item.id == "claude-sonnet-5" for item in providers[0].model_catalog)


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


def test_binding_configs_reject_plaintext_credentials_and_unknown_provider_keys():
    with pytest.raises(ValueError, match="inline credential"):
        ModelBinding(config={"api_key": "sk-plaintext"})

    with pytest.raises(ValueError, match="inline credential"):
        ModelBinding(config={"api_key_env": "OPENAI_API_KEY"})

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

    registry = PluginRegistry()
    register_builtins(registry)
    with pytest.raises(PluginBindingError):
        registry.validate_binding(
            "openai_compatible",
            PluginKind.PROVIDER,
            {"api_key_env": "OPENAI_API_KEY"},
        )
