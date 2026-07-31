import asyncio
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.settings import Settings
from test_support import register_test_provider


def make_client(tmp_path: Path) -> TestClient:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app = create_app(
        Settings(
            database_path=str(tmp_path / "configuration.db"),
            credential_master_key="test-master-key",
        )
    )
    register_test_provider(app.state.container.registry)
    return TestClient(app)


def test_model_configs_are_encrypted_and_tenant_scoped(tmp_path):
    database_path = tmp_path / "configuration.db"
    with make_client(tmp_path) as client:
        secret = "sk-test-never-return-this"
        created = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_primary",
                "name": "Primary OpenAI",
                "provider": "openai_compatible",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "secret": secret,
            },
        )
        assert created.status_code == 201
        assert secret not in created.text
        assert created.json()["masked_secret"] == "sk-…this"
        assert client.get("/api/v1/model-configs/cfg_primary").json()["masked_secret"] == "sk-…this"
        assert client.get(
            "/api/v1/model-configs/cfg_primary", headers={"X-Tenant-ID": "other"}
        ).status_code == 404

        raw = sqlite3.connect(database_path).execute(
            "SELECT secret_ciphertext, metadata_json FROM model_configs"
        ).fetchone()
        assert raw is not None
        assert secret not in raw[0]
        assert secret not in raw[1]
        tables = {
            row[0]
            for row in sqlite3.connect(database_path).execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "credential_profiles" not in tables
        assert "model_profiles" not in tables


def test_agents_require_enabled_model_config(tmp_path):
    with make_client(tmp_path) as client:
        missing = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_missing_config",
                "name": "Missing Config Agent",
                "system_prompt": "Must fail closed.",
                "model": {"model_config_id": "cfg_missing"},
            },
        )
        assert missing.status_code == 422

        disabled = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_disabled",
                "name": "Disabled connection",
                "provider": "test.deterministic",
                "model": "deterministic",
                "enabled": False,
            },
        )
        assert disabled.status_code == 201
        rejected = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_disabled_config",
                "name": "Disabled Config Agent",
                "system_prompt": "Must fail closed.",
                "model": {"model_config_id": "cfg_disabled"},
            },
        )
        assert rejected.status_code == 422

        enabled = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_enabled",
                "name": "Enabled connection",
                "provider": "test.deterministic",
                "model": "deterministic",
            },
        )
        assert enabled.status_code == 201
        accepted = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_enabled_config",
                "name": "Enabled Config Agent",
                "system_prompt": "Use the database connection.",
                "model": {"model_config_id": "cfg_enabled"},
            },
        )
        assert accepted.status_code == 201
        assert accepted.json()["model"] == {"model_config_id": "cfg_enabled", "config": {}}


def test_model_config_delete_is_guarded_by_agent_revisions(tmp_path):
    with make_client(tmp_path) as client:
        created = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_referenced",
                "name": "Referenced connection",
                "provider": "test.deterministic",
                "model": "deterministic",
            },
        )
        assert created.status_code == 201
        agent = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_referencing_config",
                "name": "Referencing Agent",
                "system_prompt": "Use the selected connection.",
                "model": {"model_config_id": "cfg_referenced"},
            },
        )
        assert agent.status_code == 201
        assert client.delete("/api/v1/model-configs/cfg_referenced").status_code == 409

        assert client.delete("/api/v1/agents/agt_referencing_config").status_code == 204
        # Historical revisions remain durable, so the reference guard is
        # intentionally still active after deleting the latest Agent row.
        assert client.delete("/api/v1/model-configs/cfg_referenced").status_code == 409
        unused = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_unused",
                "name": "Unused connection",
                "provider": "test.deterministic",
                "model": "deterministic",
            },
        )
        assert unused.status_code == 201
        assert client.delete("/api/v1/model-configs/cfg_unused").status_code == 204


def test_openai_model_configs_require_database_credentials(tmp_path):
    with make_client(tmp_path) as client:
        profile = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_openai_without_secret",
                "name": "Invalid OpenAI connection",
                "provider": "openai_compatible",
                "model": "gpt-4o-mini",
            },
        )
        assert profile.status_code == 422


def test_runtime_config_is_versioned_and_rejects_secrets(tmp_path):
    with make_client(tmp_path) as client:
        first = client.patch(
            "/api/v1/runtime-config",
            json={"key": "ui.page_size", "value": 50},
        )
        assert first.status_code == 200
        assert first.json()["version"] == 1
        updated = client.patch(
            "/api/v1/runtime-config",
            json={"key": "ui.page_size", "value": 100, "expected_version": 1},
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        stale = client.patch(
            "/api/v1/runtime-config",
            json={"key": "ui.page_size", "value": 200, "expected_version": 1},
        )
        assert stale.status_code == 409
        rejected = client.patch(
            "/api/v1/runtime-config",
            json={"key": "ui.secret", "value": {"api_key": "sk-inline"}},
        )
        assert rejected.status_code == 422
