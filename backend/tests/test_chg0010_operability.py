import asyncio
import json
import sqlite3
from pathlib import Path

from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.models import ModelConnectionCheckResult, PluginKind, PluginManifest
from uai_forge.settings import Settings
from test_support import DeterministicTestProvider, register_test_provider


def make_client(tmp_path: Path) -> TestClient:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app = create_app(
        Settings(
            database_path=str(tmp_path / "chg0010.db"),
            credential_master_key="chg0010-master-key",
        )
    )
    register_test_provider(app.state.container.registry)
    return TestClient(app)


def test_chg0010_public_contract_schemas_are_valid():
    root = Path(__file__).resolve().parents[2]
    schema_paths = [
        root / "specs/current/foundation/contracts/setup-status.schema.json",
        root / "specs/current/foundation/contracts/capability-status-v1.schema.json",
        root / "specs/current/foundation/contracts/readiness-v1.schema.json",
        root / "specs/current/foundation/contracts/model-config-v2.schema.json",
        root / "specs/current/foundation/contracts/problem-details-v1.schema.json",
        root / "specs/current/foundation/contracts/evidence-summary-v1.schema.json",
    ]
    for path in schema_paths:
        Draft202012Validator.check_schema(json.loads(path.read_text()))


def create_test_config(client: TestClient, config_id: str = "cfg_test") -> dict:
    response = client.post(
        "/api/v1/model-configs",
        json={
            "id": config_id,
            "name": "Deterministic connection",
            "provider": "test.deterministic",
            "model": "deterministic",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_setup_status_and_capability_maturity(tmp_path):
    with make_client(tmp_path) as client:
        setup = client.get("/api/v1/setup-status")
        assert setup.status_code == 200
        payload = setup.json()
        assert payload["connection"] == "connected"
        assert payload["next_action"] == "create_model_config"
        assert payload["model_connections"]["total"] == 0
        assert payload["agents"]["total"] == 0

        capabilities = client.get("/api/v1/capabilities").json()
        states = {item["id"]: item["state"] for item in capabilities}
        assert states["sqlite_event_replay"] == "implemented"
        assert states["control_api_key"] == "partial"
        assert states["checkpoint_outbox_recovery"] == "planned"


def test_model_config_lifecycle_cas_and_secret_actions_are_explicit(tmp_path):
    database_path = tmp_path / "chg0010.db"
    with make_client(tmp_path) as client:
        canary = "chg0010-secret-canary"
        created = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_secret",
                "name": "Secret connection",
                "provider": "test.deterministic",
                "model": "deterministic",
                "secret": canary,
                "secret_action": "replace",
            },
        )
        assert created.status_code == 201
        assert canary not in created.text
        assert created.json()["version"] == 1
        assert created.json()["masked_secret"] == "chg…nary"
        assert created.json()["lifecycle"] == "enabled"

        cleared = client.patch(
            "/api/v1/model-configs/cfg_secret",
            json={"expected_version": 1, "secret_action": "clear"},
        )
        assert cleared.status_code == 200
        assert cleared.json()["version"] == 2
        assert cleared.json()["masked_secret"] == ""
        assert canary not in cleared.text

        replaced = client.patch(
            "/api/v1/model-configs/cfg_secret",
            json={
                "expected_version": 2,
                "secret_action": "replace",
                "secret": "replacement-canary",
            },
        )
        assert replaced.status_code == 200
        assert "replacement-canary" not in replaced.text
        assert replaced.json()["version"] == 3

        conflict = client.patch(
            "/api/v1/model-configs/cfg_secret",
            json={"expected_version": 1, "name": "stale writer"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "resource.version_conflict"
        assert conflict.json()["retryable"] is True
        assert "replacement-canary" not in conflict.text

        raw = sqlite3.connect(database_path).execute(
            "SELECT secret_ciphertext, config_json, metadata_json FROM model_configs WHERE id = 'cfg_secret'"
        ).fetchone()
        assert raw is not None
        assert "replacement-canary" not in json.dumps(raw)


def test_verified_credentialed_config_can_be_enabled_with_secret_keep(tmp_path):
    with make_client(tmp_path) as client:
        manifest = PluginManifest(
            id="test.credentialed",
            kind=PluginKind.PROVIDER,
            display_name="Credentialed test provider",
            api_protocol="test_credentialed",
            credential_required=True,
            connection_check="remote",
            config_schema={"type": "object", "additionalProperties": False},
        )

        class CredentialedProvider(DeterministicTestProvider):
            async def check_connection(self, request):
                return ModelConnectionCheckResult(
                    status="passed",
                    code="test.connection_ok",
                    provider=request.provider,
                    model=request.model,
                )

        CredentialedProvider.manifest = manifest
        client.app.state.container.registry.register_provider(
            manifest,
            lambda binding: CredentialedProvider(),
        )

        created = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_enable_after_check",
                "name": "Enable after check",
                "provider": "test.credentialed",
                "model": "deterministic",
                "secret": "enable-canary",
                "secret_action": "replace",
            },
        )
        assert created.status_code == 201
        assert created.json()["lifecycle"] == "draft"

        checked = client.post("/api/v1/model-configs/cfg_enable_after_check/checks")
        assert checked.status_code == 200
        assert checked.json()["status"] == "passed"
        verified = client.get("/api/v1/model-configs/cfg_enable_after_check").json()
        assert verified["lifecycle"] == "verified"
        assert verified["enabled"] is False

        enabled = client.patch(
            "/api/v1/model-configs/cfg_enable_after_check",
            json={
                "expected_version": verified["version"],
                "lifecycle": "enabled",
                "enabled": True,
                "secret_action": "keep",
            },
        )
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["lifecycle"] == "enabled"
        assert enabled.json()["enabled"] is True
        assert "enable-canary" not in enabled.text


def test_connection_check_is_secret_free_and_unsupported_is_partial(tmp_path):
    with make_client(tmp_path) as client:
        created = create_test_config(client, "cfg_partial")
        check = client.post("/api/v1/model-configs/cfg_partial/checks")
        assert check.status_code == 200
        assert check.json()["status"] == "partial"
        assert check.json()["code"] == "provider.connection_check_unsupported"
        assert "credential" not in check.json()
        current = client.get("/api/v1/model-configs/cfg_partial").json()
        assert current["version"] == created["version"]
        assert current["verification"]["status"] == "never"


def test_credential_provider_cannot_be_created_enabled_without_preflight(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_bypass",
                "name": "Preflight required",
                "provider": "openai_compatible",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "secret": "preflight-canary",
                "lifecycle": "enabled",
            },
        )
        assert response.status_code == 409
        assert response.json()["code"] == "resource.conflict"
        assert "preflight-canary" not in response.text
        assert client.get("/api/v1/model-configs/cfg_bypass").status_code == 404


def test_setup_readiness_references_and_problem_details(tmp_path):
    with make_client(tmp_path) as client:
        draft = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_draft",
                "name": "Draft connection",
                "provider": "openai_compatible",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "secret": "draft-canary",
            },
        )
        assert draft.status_code == 201
        assert draft.json()["lifecycle"] == "draft"
        assert client.get("/api/v1/setup-status").json()["next_action"] == "verify_model_config"

        created = create_test_config(client, "cfg_ready")
        agent = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_ready",
                "name": "Ready Agent",
                "system_prompt": "Use a persisted connection.",
                "model": {"model_config_id": created["id"]},
            },
        )
        assert agent.status_code == 201
        readiness = client.get("/api/v1/agents/agt_ready/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["runnable"] is True
        refs = client.get("/api/v1/model-configs/cfg_ready/references")
        assert refs.status_code == 200
        assert refs.json()["total"] == 1
        assert refs.json()["items"][0]["agent_id"] == "agt_ready"

        missing = client.get("/api/v1/agents/not_here/readiness")
        assert missing.status_code == 200
        assert missing.json()["runnable"] is False
        assert missing.json()["issues"][0]["code"] == "agent.missing"

        invalid = client.post("/api/v1/runs", json={"input": "no target"})
        assert invalid.status_code == 422
        problem = invalid.json()
        assert problem["type"] == "uai-forge.problem/1.0"
        assert problem["code"] == "request.invalid"
        assert problem["field_errors"]
        assert problem["correlation_id"]
        assert "no target" not in invalid.text


def test_secret_canary_stays_out_of_error_and_diagnostic_surfaces(tmp_path):
    canary = "secret-canary-never-public"
    with make_client(tmp_path) as client:
        rejected = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_private",
                "name": "Private endpoint",
                "provider": "openai_compatible",
                "model": "gpt-4o-mini",
                "base_url": "http://127.0.0.1:9/v1",
                "secret": canary,
                "secret_action": "replace",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["code"] == "endpoint.private_address_not_allowed"
        assert canary not in rejected.text

        created = client.post(
            "/api/v1/model-configs",
            json={
                "id": "cfg_diagnostic",
                "name": "Diagnostic connection",
                "provider": "test.deterministic",
                "model": "deterministic",
                "secret": canary,
                "secret_action": "replace",
            },
        )
        assert created.status_code == 201
        for endpoint in (
            "/api/v1/model-configs",
            "/api/v1/setup-status",
            "/api/v1/capabilities",
            "/api/v1/model-configs/cfg_diagnostic/references",
        ):
            response = client.get(endpoint)
            assert canary not in response.text
