"""Run submission, concurrency and terminal-state management."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional, Set, Tuple

from .graph import AgentGraphValidator
from .models import (
    AgentInstance,
    AgentSpec,
    EventType,
    InstanceStatus,
    RunEvent,
    RunRecord,
    RunRequest,
    RunStatus,
    build_effective_agent_spec,
    utc_now,
)
from .ports import EventBusPort, RepositoryPort
from .runtime import AgentRuntime


class InvalidTopologyError(ValueError):
    pass


class RunManager:
    def __init__(
        self,
        repository: RepositoryPort,
        runtime: AgentRuntime,
        events: EventBusPort,
        validator: AgentGraphValidator,
    ) -> None:
        self.repository = repository
        self.runtime = runtime
        self.events = events
        self.validator = validator
        self._tasks: Dict[Tuple[str, str], asyncio.Task] = {}
        self._active_sessions: Set[Tuple[str, str]] = set()
        self._instance_semaphores: Dict[Tuple[str, str], asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def _resolve_target(
        self, tenant_id: str, request: RunRequest
    ) -> Tuple[AgentSpec, Optional[AgentInstance]]:
        instance: Optional[AgentInstance] = None
        if request.instance_id:
            instance = await self.repository.get_instance(tenant_id, request.instance_id)
            if instance is None:
                raise LookupError(f"instance not found: {request.instance_id}")
            if instance.status != InstanceStatus.READY:
                raise ValueError(f"instance is not ready: {instance.status.value}")
            spec = await self.repository.get_agent(
                tenant_id, instance.agent_id, instance.agent_revision
            )
        else:
            spec = await self.repository.get_agent(tenant_id, request.agent_id)
        if spec is None:
            raise LookupError("agent target not found")
        topology = await self.validator.validate(tenant_id, spec.id, spec.revision)
        if not topology.valid:
            messages = "; ".join(issue.message for issue in topology.issues)
            raise InvalidTopologyError(messages)
        if instance is not None:
            spec = build_effective_agent_spec(spec, instance.config_overrides)
        # Fail before persisting a Run. AgentRuntime repeats this validation for
        # root and child frames loaded through any RepositoryPort.
        self.runtime.validate_agent_spec(spec)
        return spec, instance

    async def start(self, tenant_id: str, request: RunRequest) -> RunRecord:
        spec, instance = await self._resolve_target(tenant_id, request)
        session_key = (tenant_id, request.session_id)
        async with self._lock:
            if session_key in self._active_sessions:
                raise ValueError("one active run per session is allowed")
            self._active_sessions.add(session_key)

        run = RunRecord(
            tenant_id=tenant_id,
            agent_id=spec.id,
            instance_id=instance.id if instance else None,
            session_id=request.session_id,
            input=request.input,
            metrics={
                "request_metadata": request.metadata,
                # Tool approvals are server-owned capabilities. The 0.1 control
                # plane has no approval resource, so confirm tools fail closed.
                "approved_tools": [],
                "root_revision": spec.revision,
                "instance_id": instance.id if instance else None,
                "environment": instance.environment if instance else None,
                "effective_policy": spec.policy.model_dump(mode="json"),
            },
        )
        await self.repository.create_run(run)
        task = asyncio.create_task(
            self._drive(run, spec, instance),
            name=f"uai-forge-run-{run.id}",
        )
        async with self._lock:
            self._tasks[(tenant_id, run.id)] = task
        task.add_done_callback(
            lambda _: asyncio.create_task(self._forget(tenant_id, run.id, request.session_id))
        )
        return run

    async def _forget(self, tenant_id: str, run_id: str, session_id: str) -> None:
        async with self._lock:
            self._tasks.pop((tenant_id, run_id), None)
            self._active_sessions.discard((tenant_id, session_id))

    async def _drive(
        self,
        run: RunRecord,
        spec: AgentSpec,
        instance: Optional[AgentInstance],
    ) -> None:
        semaphore = None
        if instance:
            key = (run.tenant_id, instance.id)
            semaphore = self._instance_semaphores.setdefault(
                key, asyncio.Semaphore(instance.max_concurrency)
            )

        async def execute() -> None:
            running = run.model_copy(
                update={"status": RunStatus.RUNNING, "started_at": utc_now()}
            )
            await self.repository.update_run(running)
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_STARTED,
                    agent_id=spec.id,
                    payload={
                        "agent_revision": spec.revision,
                        "instance_id": run.instance_id,
                        "environment": running.metrics.get("environment"),
                        "session_id": run.session_id,
                    },
                ),
            )
            output, metrics = await asyncio.wait_for(
                self.runtime.execute(running, spec),
                timeout=spec.policy.timeout_seconds,
            )
            completed = running.model_copy(
                update={
                    "status": RunStatus.SUCCEEDED,
                    "output": output,
                    "metrics": {**running.metrics, **metrics},
                    "finished_at": utc_now(),
                }
            )
            await self.repository.update_run(completed)
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_COMPLETED,
                    agent_id=spec.id,
                    payload={"output": output, "metrics": metrics},
                ),
            )

        try:
            if semaphore:
                async with semaphore:
                    await execute()
            else:
                await execute()
        except asyncio.CancelledError:
            current = await self.repository.get_run(run.tenant_id, run.id)
            cancelled = (current or run).model_copy(
                update={"status": RunStatus.CANCELLED, "finished_at": utc_now()}
            )
            await self.repository.update_run(cancelled)
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_CANCELLED,
                    agent_id=spec.id,
                    payload={"reason": "cancelled by caller"},
                ),
            )
        except Exception as exc:
            current = await self.repository.get_run(run.tenant_id, run.id)
            failed = (current or run).model_copy(
                update={
                    "status": RunStatus.FAILED,
                    "error": str(exc),
                    "finished_at": utc_now(),
                }
            )
            await self.repository.update_run(failed)
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_FAILED,
                    agent_id=spec.id,
                    payload={"error": str(exc), "error_type": type(exc).__name__},
                ),
            )

    async def cancel(self, tenant_id: str, run_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get((tenant_id, run_id))
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def wait(self, tenant_id: str, run_id: str) -> Optional[RunRecord]:
        async with self._lock:
            task = self._tasks.get((tenant_id, run_id))
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass
        return await self.repository.get_run(tenant_id, run_id)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
