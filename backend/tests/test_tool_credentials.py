import asyncio
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.settings import Settings
from uai_forge.storage import SQLiteRepository
from test_support import register_test_provider


def make_client(tmp_path: Path) -> TestClient:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app = create_app(
        Settings(
            database_path=str(tmp_path / "configuration.db"),
            credential_master_key="tool-credential-test-master",
        )
    )
    register_test_provider(app.state.container.registry)
    return TestClient(app)


def create_credential(client: TestClient, credential_id: str = "cred_github"):
    return client.post(
        "/api/v1/tool-credentials",
        json={
            "id": credential_id,
            "name": "GitHub deployment token",
            "provider": "github",
            "kind": "git_token",
            "secret": "fixture-token-never-real",
            "secret_action": "replace",
            "metadata": {"scope": "repo:example/uai"},
        },
    )


def test_tool_credentials_are_encrypted_masked_and_tenant_scoped(tmp_path):
    database_path = tmp_path / "configuration.db"
    secret = "fixture-token-never-real"
    with make_client(tmp_path) as client:
        created = create_credential(client)
        assert created.status_code == 201
        assert secret not in created.text
        assert created.json()["masked_secret"] == "fix…real"
        assert client.get("/api/v1/tool-credentials/cred_github").json()["masked_secret"] == "fix…real"
        assert client.get(
            "/api/v1/tool-credentials/cred_github",
            headers={"X-Tenant-ID": "other"},
        ).status_code == 404

        raw = sqlite3.connect(database_path).execute(
            "SELECT secret_ciphertext, metadata_json FROM tool_credentials"
        ).fetchone()
        assert raw is not None
        assert secret not in raw[0]
        assert secret not in raw[1]


def test_tool_credential_rotation_uses_cas_and_clear_disables(tmp_path):
    with make_client(tmp_path) as client:
        created = create_credential(client).json()
        rotated = client.patch(
            "/api/v1/tool-credentials/cred_github",
            json={
                "expected_version": created["version"],
                "secret": "rotated-fixture-token",
                "secret_action": "replace",
            },
        )
        assert rotated.status_code == 200
        assert rotated.json()["masked_secret"] == "rot…oken"
        assert "rotated-fixture-token" not in rotated.text

        stale = client.patch(
            "/api/v1/tool-credentials/cred_github",
            json={
                "expected_version": created["version"],
                "name": "stale update",
            },
        )
        assert stale.status_code == 409
        assert "rotated-fixture-token" not in stale.text

        cleared = client.patch(
            "/api/v1/tool-credentials/cred_github",
            json={
                "expected_version": rotated.json()["version"],
                "secret_action": "clear",
            },
        )
        assert cleared.status_code == 200
        assert cleared.json()["masked_secret"] == ""
        assert cleared.json()["enabled"] is False

        reenabled = client.patch(
            "/api/v1/tool-credentials/cred_github",
            json={
                "expected_version": cleared.json()["version"],
                "enabled": True,
            },
        )
        assert reenabled.status_code == 422


def test_tool_credential_resolver_is_internal_and_rejects_disabled(tmp_path):
    with make_client(tmp_path) as client:
        created = create_credential(client).json()
        repository = client.app.state.container.repository._delegate
        resolved = asyncio.run(
            repository.resolve_tool_credential_secret("default", created["id"])
        )
        assert resolved == "fixture-token-never-real"
        assert not any(
            route.path.endswith("/secret") for route in client.app.routes
        )

        disabled = client.patch(
            "/api/v1/tool-credentials/cred_github",
            json={
                "expected_version": created["version"],
                "enabled": False,
            },
        )
        assert disabled.status_code == 200
        assert asyncio.run(
            repository.resolve_tool_credential_secret("default", "cred_github")
        ) is None
        assert asyncio.run(
            repository.resolve_tool_credential_secret(
                "default", "cred_github", include_disabled=True
            )
        ) == "fixture-token-never-real"


def test_tool_credential_delete_is_guarded_by_agent_revisions(tmp_path):
    with make_client(tmp_path) as client:
        assert create_credential(client, "cred_referenced").status_code == 201
        model = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_for_credential_reference",
                "name": "Test model",
                "provider": "test.deterministic",
                "model": "deterministic",
            },
        )
        assert model.status_code == 201
        agent = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_credential_reference",
                "name": "Credential reference agent",
                "system_prompt": "Use a credential reference only.",
                "model": {"model_config_id": "cfg_for_credential_reference"},
                "tools": [
                    {
                        "plugin_id": "tool.echo",
                        "config": {"credential_ref": "cred_referenced"},
                    }
                ],
            },
        )
        assert agent.status_code == 201
        references = client.get("/api/v1/tool-credentials/cred_referenced/references")
        assert references.status_code == 200
        assert references.json()["total"] == 1
        assert references.json()["items"][0]["path"] == "tools[0].config.credential_ref"
        assert client.delete("/api/v1/tool-credentials/cred_referenced").status_code == 409


def test_v3_database_gets_additive_tool_credentials_migration(tmp_path):
    database_path = tmp_path / "configuration.db"
    repository = SQLiteRepository(
        str(database_path), credential_master_key="migration-test-master"
    )
    asyncio.run(repository.initialize())
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP INDEX IF EXISTS idx_tool_credentials_tenant_name")
        connection.execute("DROP TABLE tool_credentials")
        connection.execute(
            "UPDATE schema_meta SET version = 3 WHERE component = 'sqlite'"
        )
        connection.execute(
            "INSERT INTO runtime_configs (tenant_id, key, value_json, version, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("default", "migration.marker", '"kept"', 1, "2026-08-02T00:00:00+00:00"),
        )

    asyncio.run(repository.initialize())
    status = asyncio.run(repository.compatibility_status())
    assert status["version"] == 4
    assert status["status"] == "compatible"
    assert asyncio.run(repository.get_runtime_config("default", "migration.marker")) is not None
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tool_credentials'"
        ).fetchone()
