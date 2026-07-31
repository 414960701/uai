import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.settings import Settings


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                database_path=str(tmp_path / "configuration.db"),
                credential_master_key="test-master-key",
                seed_demo=True,
            )
        )
    )


def test_credentials_are_encrypted_and_tenant_scoped(tmp_path):
    database_path = tmp_path / "configuration.db"
    with make_client(tmp_path) as client:
        secret = "sk-test-never-return-this"
        created = client.post(
            "/api/v1/credentials",
            json={
                "id": "cred_primary",
                "name": "Primary OpenAI",
                "provider": "openai_compatible",
                "secret": secret,
            },
        )
        assert created.status_code == 201
        assert secret not in created.text
        assert created.json()["masked_value"] == "sk-…this"

        assert client.get("/api/v1/credentials/cred_primary").json()["masked_value"] == "sk-…this"
        assert client.get(
            "/api/v1/credentials/cred_primary", headers={"X-Tenant-ID": "other"}
        ).status_code == 404
        invalid = client.post(
            "/api/v1/credentials",
            json={
                "name": "Bad credential",
                "provider": "openai_compatible",
                "secret": "",
            },
        )
        assert invalid.status_code == 422
        assert secret not in invalid.text

        raw = sqlite3.connect(database_path).execute(
            "SELECT secret_ciphertext, metadata_json FROM credential_profiles"
        ).fetchone()
        assert secret not in raw[0]
        assert secret not in raw[1]


def test_multiple_model_profiles_and_references_are_database_backed(tmp_path):
    with make_client(tmp_path) as client:
        credential = client.post(
            "/api/v1/credentials",
            json={
                "id": "cred_for_model",
                "name": "Model credential",
                "provider": "openai_compatible",
                "api_key": "sk-model-secret",
            },
        )
        assert credential.status_code == 201
        profile = client.post(
            "/api/v1/model-profiles",
            json={
                "id": "mdl_db_mock",
                "name": "DB mock profile",
                "provider": "mock",
                "model": "deterministic",
            },
        )
        assert profile.status_code == 201
        profile_with_credential = client.post(
            "/api/v1/model-profiles",
            json={
                "id": "mdl_db_openai",
                "name": "DB OpenAI profile",
                "provider": "openai_compatible",
                "model": "gpt-test",
                "credential_profile_id": "cred_for_model",
                "base_url": "https://example.invalid/v1",
            },
        )
        assert profile_with_credential.status_code == 201

        agent = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_profile_agent",
                "name": "Profile Agent",
                "system_prompt": "Use the selected database profile.",
                "model": {
                    "provider": "mock",
                    "model": "ignored-by-profile",
                    "profile_id": "mdl_db_mock",
                },
            },
        )
        assert agent.status_code == 201
        assert agent.json()["model"]["profile_id"] == "mdl_db_mock"

        run = client.post(
            "/api/v1/runs",
            json={"agent_id": "agt_profile_agent", "input": "database profile run"},
        )
        assert run.status_code == 202
        for _ in range(50):
            latest = client.get(f"/api/v1/runs/{run.json()['id']}").json()
            if latest["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        assert latest["status"] == "succeeded"
        assert "sk-model-secret" not in str(latest)

        assert client.delete("/api/v1/credentials/cred_for_model").status_code == 409
        assert client.delete("/api/v1/model-profiles/mdl_db_mock").status_code == 409


def test_openai_profiles_require_database_credentials(tmp_path):
    with make_client(tmp_path) as client:
        profile = client.post(
            "/api/v1/model-profiles",
            json={
                "id": "mdl_openai_without_credential",
                "name": "Invalid OpenAI profile",
                "provider": "openai_compatible",
                "model": "gpt-test",
            },
        )
        assert profile.status_code == 422

        agent = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_openai_without_profile",
                "name": "Invalid OpenAI Agent",
                "system_prompt": "Must fail closed before a run.",
                "model": {
                    "provider": "openai_compatible",
                    "model": "gpt-test",
                },
            },
        )
        assert agent.status_code == 422


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
