"""SQLite persistence adapter used by the local control plane.

The class structurally implements the core ``RepositoryPort`` and
``EventStorePort`` contracts. It also exposes local control-plane CRUD methods;
those administrative methods are deliberately outside the smaller runtime
ports.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any, Callable, List, Optional, TypeVar

from .models import (
    AgentInstance,
    AgentSpec,
    RunEvent,
    RunRecord,
    RunStatus,
    utc_now,
)

T = TypeVar("T")


class RevisionConflictError(ValueError):
    pass


class RecordNotFoundError(LookupError):
    pass


class SQLiteRepository:
    def __init__(self, path: str) -> None:
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = asyncio.Lock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    async def _read(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        def runner() -> T:
            with self._connect() as connection:
                return operation(connection)

        return await asyncio.to_thread(runner)

    async def _write(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        async with self._write_lock:
            def runner() -> T:
                with self._connect() as connection:
                    result = operation(connection)
                    connection.commit()
                    return result

            return await asyncio.to_thread(runner)

    async def initialize(self) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    tenant_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE TABLE IF NOT EXISTS agent_revisions (
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, agent_id, revision)
                );
                CREATE TABLE IF NOT EXISTS instances (
                    tenant_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    instance_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    tenant_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    instance_id TEXT,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    PRIMARY KEY (tenant_id, id)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_tenant_created
                    ON runs (tenant_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS run_events (
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, run_id, sequence)
                );
                """
            )

        await self._write(operation)

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
        rows = await self._read(
            lambda connection: connection.execute(
                """
                SELECT spec_json FROM agent_revisions
                WHERE tenant_id = ? AND agent_id = ?
                ORDER BY revision DESC
                """,
                (tenant_id, agent_id),
            ).fetchall()
        )
        return [AgentSpec.model_validate_json(row["spec_json"]) for row in rows]

    async def save_agent(
        self,
        tenant_id: str,
        spec: AgentSpec,
        expected_revision: Optional[int] = None,
    ) -> AgentSpec:
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
                saved = spec.model_copy(
                    update={
                        "tenant_id": tenant_id,
                        "revision": int(current["revision"]) + 1,
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
                    tenant_id, agent_id, revision, spec_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_id, saved.id, saved.revision, payload, now.isoformat()),
            )
            return saved

        return await self._write(operation)

    async def delete_agent(self, tenant_id: str, agent_id: str) -> bool:
        def operation(connection: sqlite3.Connection) -> bool:
            cursor = connection.execute(
                "DELETE FROM agents WHERE tenant_id = ? AND id = ?",
                (tenant_id, agent_id),
            )
            return cursor.rowcount > 0

        return await self._write(operation)

    async def list_instances(self, tenant_id: str) -> List[AgentInstance]:
        rows = await self._read(
            lambda connection: connection.execute(
                """
                SELECT instance_json FROM instances
                WHERE tenant_id = ? ORDER BY name COLLATE NOCASE
                """,
                (tenant_id,),
            ).fetchall()
        )
        return [AgentInstance.model_validate_json(row["instance_json"]) for row in rows]

    async def get_instance(self, tenant_id: str, instance_id: str) -> Optional[AgentInstance]:
        row = await self._read(
            lambda connection: connection.execute(
                "SELECT instance_json FROM instances WHERE tenant_id = ? AND id = ?",
                (tenant_id, instance_id),
            ).fetchone()
        )
        return AgentInstance.model_validate_json(row["instance_json"]) if row else None

    async def save_instance(self, tenant_id: str, instance: AgentInstance) -> AgentInstance:
        now = utc_now()

        def operation(connection: sqlite3.Connection) -> AgentInstance:
            current = connection.execute(
                "SELECT instance_json FROM instances WHERE tenant_id = ? AND id = ?",
                (tenant_id, instance.id),
            ).fetchone()
            created_at = (
                AgentInstance.model_validate_json(current["instance_json"]).created_at
                if current
                else now
            )
            saved = instance.model_copy(
                update={"tenant_id": tenant_id, "created_at": created_at, "updated_at": now}
            )
            connection.execute(
                """
                INSERT INTO instances (
                    tenant_id, id, agent_id, name, instance_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, id) DO UPDATE SET
                    agent_id=excluded.agent_id,
                    name=excluded.name,
                    instance_json=excluded.instance_json,
                    updated_at=excluded.updated_at
                """,
                (
                    tenant_id,
                    saved.id,
                    saved.agent_id,
                    saved.name,
                    saved.model_dump_json(),
                    saved.created_at.isoformat(),
                    saved.updated_at.isoformat(),
                ),
            )
            return saved

        return await self._write(operation)

    async def delete_instance(self, tenant_id: str, instance_id: str) -> bool:
        return await self._write(
            lambda connection: connection.execute(
                "DELETE FROM instances WHERE tenant_id = ? AND id = ?",
                (tenant_id, instance_id),
            ).rowcount
            > 0
        )

    async def create_run(self, run: RunRecord) -> RunRecord:
        def operation(connection: sqlite3.Connection) -> RunRecord:
            connection.execute(
                """
                INSERT INTO runs (
                    tenant_id, id, agent_id, instance_id, session_id, status,
                    run_json, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.tenant_id,
                    run.id,
                    run.agent_id,
                    run.instance_id,
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
