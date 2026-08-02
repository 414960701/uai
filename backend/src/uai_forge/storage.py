"""SQLite persistence adapter used by the local control plane.

The class structurally implements the core ``RepositoryPort`` and
``EventStorePort`` contracts. It also exposes local control-plane CRUD methods;
those administrative methods are deliberately outside the smaller runtime
ports.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .models import (
    AgentRevisionInfo,
    AgentSpec,
    ModelConfig,
    ModelConfigReference,
    ModelConfigReferences,
    ModelConfigVerification,
    RuntimeConfigEntry,
    ToolCredential,
    ToolCredentialReference,
    ToolCredentialReferences,
    RunEvent,
    RunRecord,
    reject_inline_secrets,
    utc_now,
)
from .secrets import SecretDecryptionError, decrypt_secret, encrypt_secret, mask_secret

T = TypeVar("T")

SCHEMA_COMPONENT = "sqlite"
CURRENT_SCHEMA_VERSION = 4
PREVIOUS_SCHEMA_VERSION = 3
LEGACY_CONFIGURATION_TABLES = {"credential_profiles", "model_profiles"}
LEGACY_AGENT_RUNTIME_TABLES = {"instances"}
REQUIRED_TABLES = {
    "agents",
    "agent_revisions",
    "runs",
    "run_events",
    "model_configs",
    "tool_credentials",
    "runtime_configs",
}


class RevisionConflictError(ValueError):
    pass


class RecordNotFoundError(LookupError):
    pass


class ConfigurationConflictError(ValueError):
    pass


class ConfigurationInUseError(ValueError):
    pass


class SchemaCompatibilityError(RuntimeError):
    """A database cannot be opened safely by this binary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SQLiteRepository:
    def __init__(self, path: str, credential_master_key: Optional[str] = None) -> None:
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Writes may be scheduled by background Run tasks while a control-plane
        # request is still publishing plan events. A thread lock keeps the
        # SQLite critical section safe even when an ASGI test client uses more
        # than one event loop; the actual blocking work remains in a worker
        # thread below.
        self._write_lock = threading.Lock()
        # The key is a bootstrap concern and is never stored in SQLite.
        self.credential_master_key = credential_master_key or (
            f"uai-forge-development-key:{self.path}"
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _connect_read_only(self) -> sqlite3.Connection:
        """Open an existing database without creating or mutating it."""

        connection = sqlite3.connect(
            f"file:{self.path}?mode=ro",
            uri=True,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    async def _read(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        def runner() -> T:
            with self._connect() as connection:
                return operation(connection)

        return await asyncio.to_thread(runner)

    async def _write(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        acquired = await asyncio.to_thread(self._write_lock.acquire)
        try:
            def runner() -> T:
                with self._connect() as connection:
                    # Start an explicit transaction before any DDL or DML so
                    # creating a fresh database is atomic. Existing databases
                    # are validated before any business read or write; this
                    # adapter never performs in-place schema migration.
                    connection.execute("BEGIN")
                    try:
                        result = operation(connection)
                        connection.commit()
                        return result
                    except BaseException:
                        connection.rollback()
                        raise

            return await asyncio.to_thread(runner)
        finally:
            if acquired:
                self._write_lock.release()

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set:
        return {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            if row["name"] != "sqlite_sequence"
        }

    @staticmethod
    def _column_names(connection: sqlite3.Connection, table: str) -> set:
        return {
            str(row["name"])
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }

    @classmethod
    def _inspect_compatibility(cls, connection: sqlite3.Connection) -> Dict[str, Any]:
        tables = cls._table_names(connection)
        legacy = sorted(tables.intersection(LEGACY_CONFIGURATION_TABLES))
        if legacy:
            raise SchemaCompatibilityError(
                "schema.legacy_model_configuration",
                "database contains pre-ADR-0007 CredentialProfile/ModelProfile tables; back up and rebuild configuration with ModelConfig",
            )
        legacy_runtime = sorted(tables.intersection(LEGACY_AGENT_RUNTIME_TABLES))
        if legacy_runtime:
            raise SchemaCompatibilityError(
                "schema.legacy_agent_runtime",
                "database contains the removed Agent Instance table; back up and rebuild with Agent latest/revision lifecycle",
            )
        if not tables:
            return {"status": "new", "version": CURRENT_SCHEMA_VERSION, "tables": []}
        if "schema_meta" not in tables:
            raise SchemaCompatibilityError(
                "schema.version_missing",
                "database has no schema_meta marker for the current lifecycle schema; back up and rebuild",
            )
        row = connection.execute(
            "SELECT version FROM schema_meta WHERE component = ?",
            (SCHEMA_COMPONENT,),
        ).fetchone()
        if row is None:
            raise SchemaCompatibilityError(
                "schema.version_missing",
                "schema_meta exists but has no sqlite component version; back up and rebuild",
            )
        version = int(row["version"])
        if version > CURRENT_SCHEMA_VERSION:
            raise SchemaCompatibilityError(
                "schema.version_too_new",
                f"database schema version {version} is newer than supported version {CURRENT_SCHEMA_VERSION}; use a compatible binary or backup",
            )
        if version < CURRENT_SCHEMA_VERSION and version != PREVIOUS_SCHEMA_VERSION:
            raise SchemaCompatibilityError(
                "schema.version_unsupported",
                f"database schema version {version} is not the current Agent lifecycle schema {CURRENT_SCHEMA_VERSION}; back up and rebuild",
            )
        if version == PREVIOUS_SCHEMA_VERSION and "tool_credentials" not in tables:
            legacy_required_tables = REQUIRED_TABLES - {"tool_credentials"}
            missing = sorted(legacy_required_tables.difference(tables))
            if missing:
                raise SchemaCompatibilityError(
                    "schema.required_table_missing",
                    "database is missing required tables: " + ", ".join(missing),
                )
            return {
                "status": "migratable",
                "version": version,
                "tables": sorted(tables),
            }
        if version < CURRENT_SCHEMA_VERSION:
            raise SchemaCompatibilityError(
                "schema.required_table_missing",
                "database is missing the tool_credentials table; back up and rebuild",
            )
        missing = sorted(REQUIRED_TABLES.difference(tables))
        if missing:
            raise SchemaCompatibilityError(
                "schema.required_table_missing",
                "database is missing required tables: " + ", ".join(missing),
            )
        required_columns = {
            "agents": {"tenant_id", "id", "revision", "name", "spec_json", "created_at", "updated_at"},
            "agent_revisions": {
                "tenant_id", "agent_id", "revision", "spec_json", "created_at", "updated_at",
                "status", "published_at",
            },
            "runs": {"tenant_id", "id", "agent_id", "session_id", "status", "run_json", "created_at", "finished_at"},
            "run_events": {"tenant_id", "run_id", "sequence", "type", "event_json", "created_at"},
            "model_configs": {
                "tenant_id", "id", "name", "provider", "protocol", "model", "base_url",
                "secret_ciphertext", "masked_secret", "config_json", "metadata_json", "enabled",
                "version", "lifecycle", "verification_json", "created_at", "updated_at",
            },
            "tool_credentials": {
                "tenant_id", "id", "name", "provider", "kind", "secret_ciphertext",
                "masked_secret", "metadata_json", "enabled", "version", "created_at", "updated_at",
            },
            "runtime_configs": {"tenant_id", "key", "value_json", "version", "updated_at"},
            "schema_meta": {"component", "version", "updated_at"},
        }
        for table, columns in required_columns.items():
            missing_columns = sorted(columns.difference(cls._column_names(connection, table)))
            if missing_columns:
                raise SchemaCompatibilityError(
                    "schema.required_column_missing",
                    f"database table {table} is missing required columns: {', '.join(missing_columns)}; back up and rebuild",
                )
        if "instance_id" in cls._column_names(connection, "runs"):
            raise SchemaCompatibilityError(
                "schema.legacy_run_target",
                "database runs table contains removed instance_id; back up and rebuild with agent_revision",
            )
        return {
            "status": "compatible",
            "version": version,
            "tables": sorted(tables),
        }

    @staticmethod
    def _create_current_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
                CREATE TABLE agents (
                    tenant_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE TABLE agent_revisions (
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    published_at TEXT,
                    PRIMARY KEY (tenant_id, agent_id, revision)
                );
                CREATE TABLE runs (
                    tenant_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_tenant_created
                    ON runs (tenant_id, created_at DESC);
                CREATE TABLE run_events (
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, run_id, sequence)
                );
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
                    config_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    version INTEGER NOT NULL DEFAULT 1,
                    lifecycle TEXT NOT NULL DEFAULT 'enabled',
                    verification_json TEXT NOT NULL DEFAULT '{"status": "never"}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE INDEX IF NOT EXISTS idx_model_configs_tenant_name
                    ON model_configs (tenant_id, name COLLATE NOCASE);
                CREATE TABLE tool_credentials (
                    tenant_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    secret_ciphertext TEXT NOT NULL,
                    masked_secret TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE INDEX IF NOT EXISTS idx_tool_credentials_tenant_name
                    ON tool_credentials (tenant_id, name COLLATE NOCASE);
                CREATE TABLE runtime_configs (
                    tenant_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, key)
                );
                CREATE TABLE schema_meta (
                    component TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
        )
        now = utc_now().isoformat()
        connection.execute(
            "INSERT INTO schema_meta (component, version, updated_at) VALUES (?, ?, ?)",
            (SCHEMA_COMPONENT, CURRENT_SCHEMA_VERSION, now),
        )

    @staticmethod
    def _migrate_v3_to_v4(connection: sqlite3.Connection) -> None:
        """Add the independent tool credential table without touching old data."""

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tool_credentials (
                tenant_id TEXT NOT NULL,
                id TEXT NOT NULL,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                kind TEXT NOT NULL,
                secret_ciphertext TEXT NOT NULL,
                masked_secret TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, id)
            );
            CREATE INDEX IF NOT EXISTS idx_tool_credentials_tenant_name
                ON tool_credentials (tenant_id, name COLLATE NOCASE);
            """
        )
        connection.execute(
            "UPDATE schema_meta SET version = ?, updated_at = ? WHERE component = ?",
            (CURRENT_SCHEMA_VERSION, utc_now().isoformat(), SCHEMA_COMPONENT),
        )

    async def initialize(self) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            compatibility = self._inspect_compatibility(connection)
            if compatibility["status"] == "new":
                self._create_current_schema(connection)
                return
            if compatibility["status"] == "migratable":
                self._migrate_v3_to_v4(connection)
                return
            # _inspect_compatibility raises before this point for every
            # unsupported database. The current schema is read-only at boot;
            # lifecycle changes require an explicit backup/rebuild.

        await self._write(operation)

    async def compatibility_status(self) -> Dict[str, Any]:
        def operation() -> Dict[str, Any]:
            if not Path(self.path).exists():
                return {"status": "new", "version": CURRENT_SCHEMA_VERSION, "tables": []}
            connection = self._connect_read_only()
            try:
                return self._inspect_compatibility(connection)
            except SchemaCompatibilityError as exc:
                return {
                    "status": "incompatible",
                    "code": exc.code,
                    "message": exc.message,
                    "remediation": {
                        "action": "backup_and_rebuild",
                        "target": "database",
                    },
                }
            finally:
                connection.close()

        return await asyncio.to_thread(operation)

    async def count_agents(self, tenant_id: str) -> int:
        return await self._read(
            lambda connection: int(
                connection.execute(
                    "SELECT COUNT(*) FROM agents WHERE tenant_id = ?", (tenant_id,)
                ).fetchone()[0]
            )
        )

    async def list_agents(self, tenant_id: str) -> List[AgentSpec]:
        rows = await self._read(
            lambda connection: connection.execute(
                "SELECT spec_json FROM agents WHERE tenant_id = ? ORDER BY name COLLATE NOCASE",
                (tenant_id,),
            ).fetchall()
        )
        return [AgentSpec.model_validate_json(row["spec_json"]) for row in rows]

    async def get_agent(
        self, tenant_id: str, agent_id: str, revision: Optional[int] = None
    ) -> Optional[AgentSpec]:
        if revision is None:
            row = await self._read(
                lambda connection: connection.execute(
                    "SELECT spec_json FROM agents WHERE tenant_id = ? AND id = ?",
                    (tenant_id, agent_id),
                ).fetchone()
            )
        else:
            row = await self._read(
                lambda connection: connection.execute(
                    """
                    SELECT spec_json FROM agent_revisions
                    WHERE tenant_id = ? AND agent_id = ? AND revision = ?
                    """,
                    (tenant_id, agent_id, revision),
                ).fetchone()
            )
        return AgentSpec.model_validate_json(row["spec_json"]) if row else None

    async def list_agent_revisions(self, tenant_id: str, agent_id: str) -> List[AgentSpec]:
        """Return revision specs for runtime and legacy internal callers."""

        records = await self.list_agent_revision_infos(tenant_id, agent_id)
        return [item.spec for item in records]

    async def list_agent_revision_infos(
        self, tenant_id: str, agent_id: str
    ) -> List[AgentRevisionInfo]:
        rows = await self._read(
            lambda connection: connection.execute(
                """
                SELECT revisions.*, agents.revision AS latest_revision
                FROM agent_revisions AS revisions
                JOIN agents
                  ON agents.tenant_id = revisions.tenant_id
                 AND agents.id = revisions.agent_id
                WHERE revisions.tenant_id = ? AND revisions.agent_id = ?
                ORDER BY revisions.revision DESC
                """,
                (tenant_id, agent_id),
            ).fetchall()
        )
        return [
            AgentRevisionInfo(
                agent_id=row["agent_id"],
                revision=int(row["revision"]),
                status=row["status"],
                is_latest=int(row["revision"]) == int(row["latest_revision"]),
                spec=AgentSpec.model_validate_json(row["spec_json"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                published_at=row["published_at"],
            )
            for row in rows
        ]

    async def get_agent_revision_info(
        self, tenant_id: str, agent_id: str, revision: int
    ) -> Optional[AgentRevisionInfo]:
        row = await self._read(
            lambda connection: connection.execute(
                """
                SELECT revisions.*, agents.revision AS latest_revision
                FROM agent_revisions AS revisions
                JOIN agents
                  ON agents.tenant_id = revisions.tenant_id
                 AND agents.id = revisions.agent_id
                WHERE revisions.tenant_id = ? AND revisions.agent_id = ? AND revisions.revision = ?
                """,
                (tenant_id, agent_id, revision),
            ).fetchone()
        )
        if row is None:
            return None
        return AgentRevisionInfo(
            agent_id=row["agent_id"],
            revision=int(row["revision"]),
            status=row["status"],
            is_latest=int(row["revision"]) == int(row["latest_revision"]),
            spec=AgentSpec.model_validate_json(row["spec_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            published_at=row["published_at"],
        )

    async def save_agent(
        self,
        tenant_id: str,
        spec: AgentSpec,
        expected_revision: Optional[int] = None,
        *,
        status: str = "draft",
    ) -> AgentSpec:
        if status not in {"draft", "published"}:
            raise ValueError("agent revision status must be draft or published")
        now = utc_now()

        def operation(connection: sqlite3.Connection) -> AgentSpec:
            current = connection.execute(
                "SELECT revision, spec_json FROM agents WHERE tenant_id = ? AND id = ?",
                (tenant_id, spec.id),
            ).fetchone()
            if current:
                current_spec = AgentSpec.model_validate_json(current["spec_json"])
                if expected_revision is None or int(current["revision"]) != expected_revision:
                    raise RevisionConflictError(
                        f"expected revision {expected_revision}; current is {current['revision']}"
                    )
                history_max = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(revision), 0) FROM agent_revisions WHERE tenant_id = ? AND agent_id = ?",
                        (tenant_id, spec.id),
                    ).fetchone()[0]
                )
                saved = spec.model_copy(
                    update={
                        "tenant_id": tenant_id,
                        # ``agents.revision`` is the mutable latest pointer.
                        # A rollback can point it at an older immutable
                        # snapshot, so the next revision must come from the
                        # history sequence rather than latest + 1.
                        "revision": max(history_max, int(current["revision"])) + 1,
                        "created_at": current_spec.created_at,
                        "updated_at": now,
                    }
                )
            else:
                if expected_revision not in (None, 0):
                    raise RevisionConflictError("cannot update an agent that does not exist")
                saved = spec.model_copy(
                    update={
                        "tenant_id": tenant_id,
                        "revision": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            payload = saved.model_dump_json()
            connection.execute(
                """
                INSERT INTO agents (
                    tenant_id, id, revision, name, spec_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, id) DO UPDATE SET
                    revision=excluded.revision,
                    name=excluded.name,
                    spec_json=excluded.spec_json,
                    updated_at=excluded.updated_at
                """,
                (
                    tenant_id,
                    saved.id,
                    saved.revision,
                    saved.name,
                    payload,
                    saved.created_at.isoformat(),
                    saved.updated_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO agent_revisions (
                    tenant_id, agent_id, revision, spec_json, created_at,
                    updated_at, status, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    saved.id,
                    saved.revision,
                    payload,
                    now.isoformat(),
                    now.isoformat(),
                    status,
                    now.isoformat() if status == "published" else None,
                ),
            )
            return saved

        return await self._write(operation)

    async def publish_agent(
        self,
        tenant_id: str,
        agent_id: str,
        expected_revision: int,
    ) -> AgentSpec:
        """Mark the current latest snapshot as published without rewriting it."""

        def operation(connection: sqlite3.Connection) -> AgentSpec:
            current = connection.execute(
                "SELECT revision, spec_json FROM agents WHERE tenant_id = ? AND id = ?",
                (tenant_id, agent_id),
            ).fetchone()
            if current is None:
                raise RecordNotFoundError(f"agent not found: {agent_id}")
            if int(current["revision"]) != expected_revision:
                raise RevisionConflictError(
                    f"expected latest revision {expected_revision}; current is {current['revision']}"
                )
            now = utc_now().isoformat()
            cursor = connection.execute(
                """
                UPDATE agent_revisions
                SET status = 'published', published_at = ?, updated_at = ?
                WHERE tenant_id = ? AND agent_id = ? AND revision = ?
                """,
                (now, now, tenant_id, agent_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise RecordNotFoundError(
                    f"agent revision not found: {agent_id}@{expected_revision}"
                )
            return AgentSpec.model_validate_json(current["spec_json"])

        return await self._write(operation)

    async def rollback_agent(
        self,
        tenant_id: str,
        agent_id: str,
        revision: int,
        expected_revision: Optional[int] = None,
    ) -> AgentSpec:
        """Move latest to an existing immutable revision without rewriting history."""

        def operation(connection: sqlite3.Connection) -> AgentSpec:
            current = connection.execute(
                "SELECT revision FROM agents WHERE tenant_id = ? AND id = ?",
                (tenant_id, agent_id),
            ).fetchone()
            if current is None:
                raise RecordNotFoundError(f"agent not found: {agent_id}")
            if expected_revision is not None and int(current["revision"]) != expected_revision:
                raise RevisionConflictError(
                    f"expected latest revision {expected_revision}; current is {current['revision']}"
                )
            target = connection.execute(
                """
                SELECT spec_json FROM agent_revisions
                WHERE tenant_id = ? AND agent_id = ? AND revision = ?
                """,
                (tenant_id, agent_id, revision),
            ).fetchone()
            if target is None:
                raise RecordNotFoundError(
                    f"agent revision not found: {agent_id}@{revision}"
                )
            latest = AgentSpec.model_validate_json(target["spec_json"])
            now = utc_now()
            connection.execute(
                """
                UPDATE agents
                SET revision = ?, name = ?, spec_json = ?, updated_at = ?
                WHERE tenant_id = ? AND id = ?
                """,
                (
                    latest.revision,
                    latest.name,
                    latest.model_dump_json(),
                    now.isoformat(),
                    tenant_id,
                    agent_id,
                ),
            )
            return latest

        return await self._write(operation)

    async def delete_agent(self, tenant_id: str, agent_id: str) -> bool:
        def operation(connection: sqlite3.Connection) -> bool:
            cursor = connection.execute(
                "DELETE FROM agents WHERE tenant_id = ? AND id = ?",
                (tenant_id, agent_id),
            )
            return cursor.rowcount > 0

        return await self._write(operation)

    # ------------------------------------------------------------------
    # Database-backed configuration.  Secrets are encrypted before SQLite
    # sees them and the public profile object never contains plaintext.

    @staticmethod
    def _model_config_from_row(row: sqlite3.Row) -> ModelConfig:
        return ModelConfig(
            id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            provider=row["provider"],
            protocol=row["protocol"],
            model=row["model"],
            base_url=row["base_url"],
            masked_secret=row["masked_secret"],
            config=json.loads(row["config_json"] or "{}"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            enabled=bool(row["enabled"]),
            version=int(row["version"]),
            lifecycle=row["lifecycle"],
            verification=ModelConfigVerification.model_validate_json(
                row["verification_json"] or '{"status": "never"}'
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_model_configs(self, tenant_id: str) -> List[ModelConfig]:
        rows = await self._read(
            lambda connection: connection.execute(
                "SELECT * FROM model_configs WHERE tenant_id = ? ORDER BY name COLLATE NOCASE",
                (tenant_id,),
            ).fetchall()
        )
        return [self._model_config_from_row(row) for row in rows]

    async def get_model_config(
        self, tenant_id: str, config_id: str
    ) -> Optional[ModelConfig]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT * FROM model_configs WHERE tenant_id = ? AND id = ?",
                (tenant_id, config_id),
            ).fetchone()
        )
        return self._model_config_from_row(row) if row else None

    async def resolve_model_config_secret(
        self, tenant_id: str, config_id: str, *, include_disabled: bool = False
    ) -> Optional[str]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT secret_ciphertext, enabled, lifecycle FROM model_configs WHERE tenant_id = ? AND id = ?",
                (tenant_id, config_id),
            ).fetchone()
        )
        if not row or (not include_disabled and (row["lifecycle"] != "enabled" or not bool(row["enabled"]))):
            return None
        try:
            return decrypt_secret(self.credential_master_key, row["secret_ciphertext"])
        except SecretDecryptionError as exc:
            raise RuntimeError("model configuration secret could not be decrypted") from exc

    async def save_model_config(
        self,
        tenant_id: str,
        config: ModelConfig,
        secret: Optional[str] = None,
        *,
        expected_version: Optional[int] = None,
        secret_action: Optional[str] = None,
    ) -> ModelConfig:
        now = utc_now()

        def operation(connection: sqlite3.Connection) -> ModelConfig:
            current = connection.execute(
                "SELECT created_at, secret_ciphertext, masked_secret, version FROM model_configs WHERE tenant_id = ? AND id = ?",
                (tenant_id, config.id),
            ).fetchone()
            if current and expected_version is None:
                raise ConfigurationConflictError("expected model configuration version is required")
            if current and int(current["version"]) != expected_version:
                raise ConfigurationConflictError(
                    f"expected version {expected_version}; current is {current['version']}"
                )
            created_at = datetime.fromisoformat(current["created_at"]) if current else now
            action = secret_action or ("replace" if secret is not None else "keep")
            if action == "replace" and secret is None:
                raise ConfigurationConflictError("secret is required for secret_action=replace")
            if action == "replace":
                encrypted = encrypt_secret(self.credential_master_key, secret or "")
                masked = mask_secret(secret or "")
            elif action == "clear":
                encrypted = ""
                masked = ""
            else:
                encrypted = current["secret_ciphertext"] if current else ""
                masked = current["masked_secret"] if current else ""
            next_version = int(current["version"]) + 1 if current else 1
            saved = config.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "masked_secret": masked,
                    "version": next_version,
                    "created_at": created_at,
                    "updated_at": now,
                }
            )
            values = (
                saved.name,
                saved.provider,
                saved.protocol,
                saved.model,
                saved.base_url,
                encrypted,
                saved.masked_secret,
                json.dumps(saved.config, ensure_ascii=False),
                json.dumps(saved.metadata, ensure_ascii=False),
                int(saved.enabled),
                saved.version,
                saved.lifecycle,
                saved.verification.model_dump_json(),
                saved.updated_at.isoformat(),
            )
            if current:
                # The row predicate is the actual CAS boundary.  The
                # process-local lock remains useful for this adapter, but it
                # must not be mistaken for concurrency correctness.
                cursor = connection.execute(
                    """
                    UPDATE model_configs SET
                        name=?, provider=?, protocol=?, model=?, base_url=?,
                        secret_ciphertext=?, masked_secret=?, config_json=?,
                        metadata_json=?, enabled=?, version=?, lifecycle=?,
                        verification_json=?, updated_at=?
                    WHERE tenant_id=? AND id=? AND version=?
                    """,
                    values + (tenant_id, saved.id, expected_version),
                )
                if cursor.rowcount != 1:
                    raise ConfigurationConflictError(
                        "model configuration changed while it was being updated"
                    )
            else:
                if expected_version not in (None, 0):
                    raise ConfigurationConflictError("model configuration does not exist")
                connection.execute(
                    """
                    INSERT INTO model_configs (
                        tenant_id, id, name, provider, protocol, model, base_url,
                        secret_ciphertext, masked_secret, config_json, metadata_json,
                        enabled, version, lifecycle, verification_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        saved.id,
                        *values,
                        saved.created_at.isoformat(),
                    ),
                )
            return saved

        return await self._write(operation)

    async def delete_model_config(self, tenant_id: str, config_id: str) -> bool:
        return await self._write(
            lambda connection: connection.execute(
                "DELETE FROM model_configs WHERE tenant_id = ? AND id = ?",
                (tenant_id, config_id),
            ).rowcount
            > 0
        )

    async def model_config_is_referenced(self, tenant_id: str, config_id: str) -> bool:
        references = await self.list_model_config_references(tenant_id, config_id, limit=1)
        return references.total > 0

    async def list_model_config_references(
        self,
        tenant_id: str,
        config_id: str,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> ModelConfigReferences:
        try:
            offset = max(0, int(cursor or "0"))
        except ValueError:
            offset = 0
        bounded_limit = min(max(limit, 1), 200)

        rows = await self._read(
            lambda connection: connection.execute(
                "SELECT spec_json FROM agent_revisions WHERE tenant_id = ? ORDER BY agent_id, revision",
                (tenant_id,),
            ).fetchall()
        )
        matches: List[ModelConfigReference] = []
        for row in rows:
            spec = AgentSpec.model_validate_json(row["spec_json"])
            if spec.model.model_config_id == config_id:
                matches.append(
                    ModelConfigReference(
                        agent_id=spec.id,
                        agent_name=spec.name,
                        revision=spec.revision,
                    )
                )
        page = matches[offset : offset + bounded_limit]
        next_cursor = str(offset + bounded_limit) if offset + bounded_limit < len(matches) else None
        return ModelConfigReferences(
            items=page,
            total=len(matches),
            next_cursor=next_cursor,
        )

    # ------------------------------------------------------------------
    # Deployment-managed tool credentials.  The public object is always a
    # masked view; only the internal resolver returns a decrypted value.

    @staticmethod
    def _tool_credential_from_row(row: sqlite3.Row) -> ToolCredential:
        return ToolCredential(
            id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            provider=row["provider"],
            kind=row["kind"],
            masked_secret=row["masked_secret"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            enabled=bool(row["enabled"]),
            version=int(row["version"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_tool_credentials(self, tenant_id: str) -> List[ToolCredential]:
        rows = await self._read(
            lambda connection: connection.execute(
                "SELECT * FROM tool_credentials WHERE tenant_id = ? ORDER BY name COLLATE NOCASE",
                (tenant_id,),
            ).fetchall()
        )
        return [self._tool_credential_from_row(row) for row in rows]

    async def get_tool_credential(
        self, tenant_id: str, credential_id: str
    ) -> Optional[ToolCredential]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT * FROM tool_credentials WHERE tenant_id = ? AND id = ?",
                (tenant_id, credential_id),
            ).fetchone()
        )
        return self._tool_credential_from_row(row) if row else None

    async def resolve_tool_credential_secret(
        self,
        tenant_id: str,
        credential_id: str,
        *,
        include_disabled: bool = False,
    ) -> Optional[str]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT secret_ciphertext, enabled FROM tool_credentials WHERE tenant_id = ? AND id = ?",
                (tenant_id, credential_id),
            ).fetchone()
        )
        if not row or (not include_disabled and not bool(row["enabled"])):
            return None
        if not row["secret_ciphertext"]:
            return None
        try:
            return decrypt_secret(self.credential_master_key, row["secret_ciphertext"])
        except SecretDecryptionError as exc:
            raise RuntimeError("tool credential could not be decrypted") from exc

    async def save_tool_credential(
        self,
        tenant_id: str,
        credential: ToolCredential,
        secret: Optional[str] = None,
        *,
        expected_version: Optional[int] = None,
        secret_action: Optional[str] = None,
    ) -> ToolCredential:
        now = utc_now()

        def operation(connection: sqlite3.Connection) -> ToolCredential:
            current = connection.execute(
                "SELECT created_at, secret_ciphertext, masked_secret, version FROM tool_credentials WHERE tenant_id = ? AND id = ?",
                (tenant_id, credential.id),
            ).fetchone()
            if current and expected_version is None:
                raise ConfigurationConflictError("expected tool credential version is required")
            if current and int(current["version"]) != expected_version:
                raise ConfigurationConflictError(
                    f"expected version {expected_version}; current is {current['version']}"
                )
            created_at = datetime.fromisoformat(current["created_at"]) if current else now
            action = secret_action or ("replace" if secret is not None else "keep")
            if action == "replace" and secret is None:
                raise ConfigurationConflictError("secret is required for secret_action=replace")
            if action == "replace":
                encrypted = encrypt_secret(self.credential_master_key, secret or "")
                masked = mask_secret(secret or "")
            elif action == "clear":
                encrypted = ""
                masked = ""
            else:
                encrypted = current["secret_ciphertext"] if current else ""
                masked = current["masked_secret"] if current else ""
            next_version = int(current["version"]) + 1 if current else 1
            saved = credential.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "masked_secret": masked,
                    "enabled": bool(credential.enabled) and action != "clear",
                    "version": next_version,
                    "created_at": created_at,
                    "updated_at": now,
                }
            )
            common_values = (
                saved.name,
                saved.provider,
                saved.kind,
                encrypted,
                saved.masked_secret,
                json.dumps(saved.metadata, ensure_ascii=False),
                int(saved.enabled),
                saved.version,
            )
            if current:
                cursor = connection.execute(
                    """
                    UPDATE tool_credentials SET
                        name=?, provider=?, kind=?, secret_ciphertext=?, masked_secret=?,
                        metadata_json=?, enabled=?, version=?, updated_at=?
                    WHERE tenant_id=? AND id=? AND version=?
                    """,
                    common_values + (saved.updated_at.isoformat(), tenant_id, saved.id, expected_version),
                )
                if cursor.rowcount != 1:
                    raise ConfigurationConflictError(
                        "tool credential changed while it was being updated"
                    )
            else:
                if expected_version not in (None, 0):
                    raise ConfigurationConflictError("tool credential does not exist")
                connection.execute(
                    """
                    INSERT INTO tool_credentials (
                        tenant_id, id, name, provider, kind, secret_ciphertext,
                        masked_secret, metadata_json, enabled, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        saved.id,
                        *common_values,
                        saved.created_at.isoformat(),
                        saved.updated_at.isoformat(),
                    ),
                )
            return saved

        return await self._write(operation)

    async def delete_tool_credential(self, tenant_id: str, credential_id: str) -> bool:
        def operation(connection: sqlite3.Connection) -> bool:
            rows = connection.execute(
                "SELECT spec_json FROM agent_revisions WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchall()
            for row in rows:
                spec = AgentSpec.model_validate_json(row["spec_json"])
                if any(
                    tool.config.get("credential_ref") == credential_id
                    for tool in spec.tools
                ):
                    raise ConfigurationInUseError(
                        "tool credential is used by an agent"
                    )
            return (
                connection.execute(
                    "DELETE FROM tool_credentials WHERE tenant_id = ? AND id = ?",
                    (tenant_id, credential_id),
                ).rowcount
                > 0
            )

        return await self._write(operation)

    async def list_tool_credential_references(
        self,
        tenant_id: str,
        credential_id: str,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> ToolCredentialReferences:
        try:
            offset = max(0, int(cursor or "0"))
        except ValueError:
            offset = 0
        bounded_limit = min(max(limit, 1), 200)
        rows = await self._read(
            lambda connection: connection.execute(
                "SELECT spec_json FROM agent_revisions WHERE tenant_id = ? ORDER BY agent_id, revision",
                (tenant_id,),
            ).fetchall()
        )
        matches: List[ToolCredentialReference] = []
        for row in rows:
            spec = AgentSpec.model_validate_json(row["spec_json"])
            for index, tool in enumerate(spec.tools):
                if tool.config.get("credential_ref") == credential_id:
                    matches.append(
                        ToolCredentialReference(
                            agent_id=spec.id,
                            agent_name=spec.name,
                            revision=spec.revision,
                            tool_plugin_id=tool.plugin_id,
                            path=f"tools[{index}].config.credential_ref",
                        )
                    )
        page = matches[offset : offset + bounded_limit]
        next_cursor = str(offset + bounded_limit) if offset + bounded_limit < len(matches) else None
        return ToolCredentialReferences(
            items=page,
            total=len(matches),
            next_cursor=next_cursor,
        )

    async def tool_credential_is_referenced(
        self, tenant_id: str, credential_id: str
    ) -> bool:
        references = await self.list_tool_credential_references(
            tenant_id, credential_id, limit=1
        )
        return references.total > 0

    async def list_runtime_configs(self, tenant_id: str) -> List[RuntimeConfigEntry]:
        rows = await self._read(
            lambda connection: connection.execute(
                "SELECT * FROM runtime_configs WHERE tenant_id = ? ORDER BY key",
                (tenant_id,),
            ).fetchall()
        )
        return [
            RuntimeConfigEntry(
                tenant_id=row["tenant_id"],
                key=row["key"],
                value=json.loads(row["value_json"]),
                version=int(row["version"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def get_runtime_config(
        self, tenant_id: str, key: str
    ) -> Optional[RuntimeConfigEntry]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT * FROM runtime_configs WHERE tenant_id = ? AND key = ?",
                (tenant_id, key),
            ).fetchone()
        )
        if not row:
            return None
        return RuntimeConfigEntry(
            tenant_id=row["tenant_id"],
            key=row["key"],
            value=json.loads(row["value_json"]),
            version=int(row["version"]),
            updated_at=row["updated_at"],
        )

    async def save_runtime_config(
        self,
        tenant_id: str,
        key: str,
        value: Any,
        expected_version: Optional[int] = None,
    ) -> RuntimeConfigEntry:
        # Keep the repository boundary safe for internal callers as well as
        # the HTTP/Pydantic boundary.  RuntimeConfig is business configuration
        # and must never become a covert plaintext credential store.
        reject_inline_secrets({"value": value})
        now = utc_now()

        def operation(connection: sqlite3.Connection) -> RuntimeConfigEntry:
            current = connection.execute(
                "SELECT version FROM runtime_configs WHERE tenant_id = ? AND key = ?",
                (tenant_id, key),
            ).fetchone()
            if current:
                current_version = int(current["version"])
                if expected_version is None or current_version != expected_version:
                    raise ConfigurationConflictError(
                        f"expected version {expected_version}; current is {current_version}"
                    )
                version = current_version + 1
            else:
                if expected_version not in (None, 0):
                    raise ConfigurationConflictError("configuration key does not exist")
                version = 1
            connection.execute(
                """
                INSERT INTO runtime_configs (tenant_id, key, value_json, version, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, key) DO UPDATE SET
                    value_json=excluded.value_json,
                    version=excluded.version,
                    updated_at=excluded.updated_at
                """,
                (tenant_id, key, json.dumps(value, ensure_ascii=False), version, now.isoformat()),
            )
            return RuntimeConfigEntry(
                tenant_id=tenant_id,
                key=key,
                value=value,
                version=version,
                updated_at=now,
            )

        return await self._write(operation)

    async def create_run(self, run: RunRecord) -> RunRecord:
        def operation(connection: sqlite3.Connection) -> RunRecord:
            connection.execute(
                """
                INSERT INTO runs (
                    tenant_id, id, agent_id, session_id, status,
                    run_json, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.tenant_id,
                    run.id,
                    run.agent_id,
                    run.session_id,
                    run.status.value,
                    run.model_dump_json(),
                    run.created_at.isoformat(),
                    None,
                ),
            )
            return run

        return await self._write(operation)

    async def update_run(self, run: RunRecord) -> RunRecord:
        def operation(connection: sqlite3.Connection) -> RunRecord:
            cursor = connection.execute(
                """
                UPDATE runs SET status = ?, run_json = ?, finished_at = ?
                WHERE tenant_id = ? AND id = ?
                """,
                (
                    run.status.value,
                    run.model_dump_json(),
                    run.finished_at.isoformat() if run.finished_at else None,
                    run.tenant_id,
                    run.id,
                ),
            )
            if cursor.rowcount == 0:
                raise RecordNotFoundError(f"run not found: {run.id}")
            return run

        return await self._write(operation)

    async def get_run(self, tenant_id: str, run_id: str) -> Optional[RunRecord]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT run_json FROM runs WHERE tenant_id = ? AND id = ?",
                (tenant_id, run_id),
            ).fetchone()
        )
        return RunRecord.model_validate_json(row["run_json"]) if row else None

    async def list_runs(self, tenant_id: str, limit: int = 100) -> List[RunRecord]:
        rows = await self._read(
            lambda connection: connection.execute(
                """
                SELECT run_json FROM runs WHERE tenant_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (tenant_id, min(max(limit, 1), 500)),
            ).fetchall()
        )
        return [RunRecord.model_validate_json(row["run_json"]) for row in rows]

    async def append_event(self, tenant_id: str, event: RunEvent) -> RunEvent:
        def operation(connection: sqlite3.Connection) -> RunEvent:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                FROM run_events WHERE tenant_id = ? AND run_id = ?
                """,
                (tenant_id, event.run_id),
            ).fetchone()
            saved = event.model_copy(update={"sequence": int(row["next_sequence"])})
            connection.execute(
                """
                INSERT INTO run_events (
                    tenant_id, run_id, sequence, type, event_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    saved.run_id,
                    saved.sequence,
                    saved.type.value,
                    saved.model_dump_json(),
                    saved.timestamp.isoformat(),
                ),
            )
            return saved

        return await self._write(operation)

    async def list_events(
        self, tenant_id: str, run_id: str, after_sequence: int = 0
    ) -> List[RunEvent]:
        rows = await self._read(
            lambda connection: connection.execute(
                """
                SELECT event_json FROM run_events
                WHERE tenant_id = ? AND run_id = ? AND sequence > ?
                ORDER BY sequence ASC
                """,
                (tenant_id, run_id, after_sequence),
            ).fetchall()
        )
        return [RunEvent.model_validate_json(row["event_json"]) for row in rows]

    async def terminal_event_exists(self, tenant_id: str, run_id: str) -> bool:
        terminal = (
            "run.completed",
            "run.failed",
            "run.cancelled",
        )
        return await self._read(
            lambda connection: connection.execute(
                """
                SELECT 1 FROM run_events
                WHERE tenant_id = ? AND run_id = ? AND type IN (?, ?, ?)
                LIMIT 1
                """,
                (tenant_id, run_id, *terminal),
            ).fetchone()
            is not None
        )
