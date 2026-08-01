import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from uai_forge.cli import _doctor
from uai_forge.endpoints import EndpointPolicyError, endpoint_summary, validate_endpoint_url
from uai_forge.settings import Settings
from uai_forge.storage import CURRENT_SCHEMA_VERSION, SQLiteRepository, SchemaCompatibilityError


def run(coroutine):
    try:
        return asyncio.run(coroutine)
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("file:///tmp/provider", "endpoint.scheme_not_allowed"),
        ("https://user:pass@example.com/v1", "endpoint.userinfo_not_allowed"),
        ("https://example.com/v1?secret=1", "endpoint.query_or_fragment_not_allowed"),
        ("http://127.0.0.1:8000/v1", "endpoint.private_address_not_allowed"),
    ],
)
def test_provider_endpoint_policy_rejects_unsafe_values(value, code):
    with pytest.raises(EndpointPolicyError) as error:
        validate_endpoint_url(value)
    assert error.value.code == code


def test_provider_endpoint_policy_allows_explicit_local_development_exception():
    assert validate_endpoint_url("http://127.0.0.1:8000/v1", allow_local=True) == "http://127.0.0.1:8000/v1"
    assert endpoint_summary("https://api.example.com/v1") == "https://api.example.com/v1"


def test_new_database_records_schema_meta_before_business_use(tmp_path: Path):
    path = tmp_path / "new.db"
    repository = SQLiteRepository(str(path))
    run(repository.initialize())
    row = sqlite3.connect(path).execute(
        "SELECT version FROM schema_meta WHERE component = 'sqlite'"
    ).fetchone()
    assert row == (CURRENT_SCHEMA_VERSION,)
    status = run(repository.compatibility_status())
    assert status["status"] == "compatible"
    assert status["version"] == CURRENT_SCHEMA_VERSION


def test_unknown_schema_version_fails_closed_and_doctor_path_is_read_only(tmp_path: Path):
    path = tmp_path / "future.db"
    repository = SQLiteRepository(str(path))
    run(repository.initialize())
    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE schema_meta SET version = ? WHERE component = 'sqlite'",
        (CURRENT_SCHEMA_VERSION + 10,),
    )
    connection.commit()
    connection.close()

    status = run(repository.compatibility_status())
    assert status["status"] == "incompatible"
    assert status["code"] == "schema.version_too_new"
    assert status["remediation"] == {"action": "backup_and_rebuild", "target": "database"}
    with pytest.raises(SchemaCompatibilityError) as error:
        run(repository.initialize())
    assert error.value.code == "schema.version_too_new"


def test_previous_schema_version_requires_explicit_backup_and_rebuild(tmp_path: Path):
    path = tmp_path / "previous-schema.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE schema_meta (component TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO schema_meta VALUES ('sqlite', ?, '2026-08-01T00:00:00+00:00')",
        (CURRENT_SCHEMA_VERSION - 1,),
    )
    connection.commit()
    connection.close()

    repository = SQLiteRepository(str(path))
    status = run(repository.compatibility_status())
    assert status["status"] == "incompatible"
    assert status["code"] == "schema.version_unsupported"
    with pytest.raises(SchemaCompatibilityError) as error:
        run(repository.initialize())
    assert error.value.code == "schema.version_unsupported"


def test_legacy_model_profile_database_is_not_silently_migrated(tmp_path: Path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE credential_profiles (id TEXT PRIMARY KEY)")
    connection.commit()
    connection.close()
    repository = SQLiteRepository(str(path))
    status = run(repository.compatibility_status())
    assert status["status"] == "incompatible"
    assert status["code"] == "schema.legacy_model_configuration"
    with pytest.raises(SchemaCompatibilityError) as error:
        run(repository.initialize())
    assert error.value.code == "schema.legacy_model_configuration"


def test_doctor_is_read_only_for_a_new_database(tmp_path: Path, capsys):
    path = tmp_path / "doctor-new.db"
    exit_code = run(
        _doctor(
            Settings(
                database_path=str(path),
                credential_master_key="doctor-test-key",
            )
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["schema"]["status"] == "new"
    assert payload["migration"] == {
        "dry_run": True,
        "writes_performed": False,
        "pending": [],
    }
    assert not path.exists()


def test_unsupported_agent_lifecycle_schema_is_rejected_without_writes(tmp_path: Path):
    path = tmp_path / "unsupported-lifecycle.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE agents (id TEXT);
        CREATE TABLE agent_revisions (id TEXT);
        CREATE TABLE instances (id TEXT);
        CREATE TABLE runs (id TEXT);
        CREATE TABLE run_events (id TEXT);
        CREATE TABLE runtime_configs (id TEXT);
        CREATE TABLE model_configs (
            tenant_id TEXT NOT NULL,
            id TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            protocol TEXT NOT NULL,
            model TEXT NOT NULL,
            base_url TEXT,
            secret_ciphertext TEXT NOT NULL,
            masked_secret TEXT NOT NULL,
            config_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, id)
        );
        CREATE TABLE schema_meta (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO schema_meta VALUES ('sqlite', 1, '2026-08-01T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    repository = SQLiteRepository(str(path), credential_master_key="lifecycle-test-key")
    status = run(repository.compatibility_status())
    assert status["status"] == "incompatible"
    assert status["code"] == "schema.legacy_agent_runtime"
    with pytest.raises(SchemaCompatibilityError) as error:
        run(repository.initialize())
    assert error.value.code == "schema.legacy_agent_runtime"

    connection = sqlite3.connect(path)
    version = connection.execute(
        "SELECT version FROM schema_meta WHERE component = 'sqlite'"
    ).fetchone()[0]
    connection.close()
    assert version == 1
