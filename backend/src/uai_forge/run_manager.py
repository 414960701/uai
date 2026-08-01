"""Run submission, concurrency and terminal-state management."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Set, Tuple

from .graph import AgentGraphValidator
from .models import (
    AgentSpec,
    ChoiceResolutionRequest,
    EventType,
    ExecutionMode,
    PlanEditRequest,
    PlanStatus,
    PlanStepStatus,
    RunEvent,
    RunRecord,
    RunRequest,
    RunStatus,
    TodoStatus,
    utc_now,
)
from .ports import EventBusPort, RepositoryPort
from .plans import build_execution_plan
from .runtime import AgentRuntime
from .interactions import extract_choice_prompt
from .tasks import build_task_todo_list, mark_todo_running, mark_todo_terminal


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
        self._lock = asyncio.Lock()

    async def _resolve_target(
        self, tenant_id: str, request: RunRequest
    ) -> AgentSpec:
        spec = await self.repository.get_agent(
            tenant_id, request.agent_id, request.agent_revision
        )
        if spec is None:
            raise LookupError("agent target not found")
        topology = await self.validator.validate(tenant_id, spec.id, spec.revision)
        if not topology.valid:
            messages = "; ".join(issue.message for issue in topology.issues)
            raise InvalidTopologyError(messages)
        # Fail before persisting a Run. AgentRuntime repeats this validation for
        # root and child frames loaded through any RepositoryPort.
        self.runtime.validate_agent_spec(spec)
        return spec

    async def start(self, tenant_id: str, request: RunRequest) -> RunRecord:
        spec = await self._resolve_target(tenant_id, request)
        session_key = (tenant_id, request.session_id)
        async with self._lock:
            if session_key in self._active_sessions:
                raise ValueError("one active run per session is allowed")
            self._active_sessions.add(session_key)

        source_plan_metrics = {
            key: request.metadata[key]
            for key in ("source_plan_id", "source_plan_run_id", "source_plan_version")
            if isinstance(request.metadata.get(key), (str, int))
        }
        run = RunRecord(
            tenant_id=tenant_id,
            agent_id=spec.id,
            agent_revision=spec.revision,
            session_id=request.session_id,
            input=request.input,
            metrics={
                "request_metadata": request.metadata,
                # Tool approvals are server-owned capabilities. The 0.1 control
                # plane has no approval resource, so confirm tools fail closed.
                "approved_tools": [],
                "root_revision": spec.revision,
                "thinking_mode": request.thinking_mode.value,
                "execution_mode": request.execution_mode.value,
                "effective_policy": spec.policy.model_dump(mode="json"),
                **source_plan_metrics,
            },
        )
        run = run.model_copy(
            update={"metrics": {**run.metrics, "trace_id": f"trace_{run.id}"}}
        )
        todo = (
            build_task_todo_list(
                run_id=run.id,
                session_id=run.session_id,
                input_text=run.input,
            )
            if request.execution_mode is ExecutionMode.EXECUTE
            else None
        )
        if todo is not None:
            run = run.model_copy(
                update={
                    "todo": todo,
                    "metrics": {
                        **run.metrics,
                        "todo_id": todo.todo_id,
                        "todo_status": todo.status.value,
                    },
                }
            )
        await self.repository.create_run(run)
        task = asyncio.create_task(
            self._drive(run, spec),
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

    async def _publish_plan_event(
        self,
        tenant_id: str,
        plan_run: RunRecord,
        event_type: EventType,
        plan: Any,
        *,
        execution_run_id: Optional[str] = None,
    ) -> None:
        payload = {"plan": plan.model_dump(mode="json")}
        if execution_run_id:
            payload["execution_run_id"] = execution_run_id
        await self.events.publish(
            tenant_id,
            RunEvent(
                run_id=plan_run.id,
                type=event_type,
                agent_id=plan_run.agent_id,
                payload=payload,
                trace_id=plan_run.metrics.get("trace_id"),
                span_id=plan_run.metrics.get("run_span_id"),
            ),
        )

    async def _publish_todo_event(
        self,
        tenant_id: str,
        run: RunRecord,
        event_type: EventType,
        todo: Any,
    ) -> None:
        await self.events.publish(
            tenant_id,
            RunEvent(
                run_id=run.id,
                type=event_type,
                agent_id=run.agent_id,
                payload={"todo": todo.model_dump(mode="json")},
                trace_id=run.metrics.get("trace_id"),
                span_id=run.metrics.get("run_span_id"),
            ),
        )

    async def _publish_choice_event(
        self,
        tenant_id: str,
        run: RunRecord,
        event_type: EventType,
    ) -> None:
        if run.choice is None:
            return
        await self.events.publish(
            tenant_id,
            RunEvent(
                run_id=run.id,
                type=event_type,
                agent_id=run.agent_id,
                payload={"choice": run.choice.model_dump(mode="json")},
                trace_id=run.metrics.get("trace_id"),
                span_id=run.metrics.get("run_span_id"),
            ),
        )

    async def _sync_source_plan(
        self,
        run: RunRecord,
        status: PlanStatus,
        *,
        execution_run_id: Optional[str] = None,
    ) -> None:
        source_run_id = run.metrics.get("source_plan_run_id")
        if not isinstance(source_run_id, str) or not source_run_id:
            return
        source = await self.repository.get_run(run.tenant_id, source_run_id)
        if source is None or source.plan is None:
            return
        current_plan = source.plan
        if current_plan.status not in {
            PlanStatus.APPROVED,
            PlanStatus.EXECUTING,
        }:
            return
        step_status = (
            PlanStepStatus.COMPLETED
            if status is PlanStatus.COMPLETED
            else PlanStepStatus.FAILED
            if status is PlanStatus.FAILED
            else PlanStepStatus.SKIPPED
        )
        updated_plan = current_plan.model_copy(
            update={
                "status": status,
                "steps": [step.model_copy(update={"status": step_status}) for step in current_plan.steps],
                "updated_at": utc_now(),
            }
        )
        updated_source = source.model_copy(
            update={
                "plan": updated_plan,
                "metrics": {
                    **source.metrics,
                    "plan_status": status.value,
                    "execution_run_id": execution_run_id or run.id,
                },
            }
        )
        await self.repository.update_run(updated_source)
        event_type = {
            PlanStatus.COMPLETED: EventType.PLAN_COMPLETED,
            PlanStatus.FAILED: EventType.PLAN_FAILED,
            PlanStatus.CANCELLED: EventType.PLAN_CANCELLED,
        }.get(status)
        if event_type:
            await self._publish_plan_event(
                run.tenant_id,
                updated_source,
                event_type,
                updated_plan,
                execution_run_id=execution_run_id or run.id,
            )

    async def edit_plan(
        self,
        tenant_id: str,
        run_id: str,
        request: PlanEditRequest,
    ) -> Any:
        run = await self.repository.get_run(tenant_id, run_id)
        if run is None:
            raise LookupError(f"run not found: {run_id}")
        if run.plan is None:
            raise ValueError("run has no reviewable plan")
        if run.plan.status not in {PlanStatus.PROPOSED, PlanStatus.NEEDS_REVISION}:
            raise ValueError("plan is no longer editable")
        if run.plan.version != request.expected_version:
            raise ValueError("plan version conflict")
        edited = run.plan.model_copy(
            update={
                "version": run.plan.version + 1,
                "title": request.title,
                "goal": request.goal,
                "assumptions": request.assumptions,
                "steps": [step.model_copy(update={"status": PlanStepStatus.PROPOSED}) for step in request.steps],
                "risks": request.risks,
                "status": PlanStatus.NEEDS_REVISION,
                "updated_at": utc_now(),
            }
        )
        updated = run.model_copy(
            update={
                "plan": edited,
                "metrics": {
                    **run.metrics,
                    "plan_id": edited.plan_id,
                    "plan_version": edited.version,
                    "plan_status": edited.status.value,
                },
            }
        )
        await self.repository.update_run(updated)
        await self._publish_plan_event(tenant_id, updated, EventType.PLAN_UPDATED, edited)
        return edited

    async def reject_plan(self, tenant_id: str, run_id: str, expected_version: int) -> Any:
        run = await self.repository.get_run(tenant_id, run_id)
        if run is None:
            raise LookupError(f"run not found: {run_id}")
        if run.plan is None:
            raise ValueError("run has no reviewable plan")
        if run.plan.version != expected_version:
            raise ValueError("plan version conflict")
        if run.plan.status not in {PlanStatus.PROPOSED, PlanStatus.NEEDS_REVISION}:
            raise ValueError("plan is no longer awaiting review")
        rejected = run.plan.model_copy(update={"status": PlanStatus.REJECTED, "updated_at": utc_now()})
        updated = run.model_copy(
            update={
                "plan": rejected,
                "metrics": {**run.metrics, "plan_status": rejected.status.value},
            }
        )
        await self.repository.update_run(updated)
        await self._publish_plan_event(tenant_id, updated, EventType.PLAN_REJECTED, rejected)
        return rejected

    async def resolve_choice(
        self,
        tenant_id: str,
        run_id: str,
        request: ChoiceResolutionRequest,
    ) -> RunRecord:
        run = await self.repository.get_run(tenant_id, run_id)
        if run is None:
            raise LookupError(f"run not found: {run_id}")
        if run.choice is None:
            raise ValueError("run has no pending choice")
        if run.choice.status != "open":
            raise ValueError("choice is no longer open")
        option_ids = {option.id for option in run.choice.options}
        selected_ids = list(dict.fromkeys(request.selected_ids))
        if any(item not in option_ids for item in selected_ids):
            raise ValueError("choice contains an unknown option")
        if request.action == "continue":
            if run.choice.selection_type == "single" and len(selected_ids) != 1:
                raise ValueError("single choice requires exactly one option")
            if run.choice.required and not selected_ids:
                raise ValueError("this choice requires an option")
        else:
            selected_ids = []
        updated_choice = run.choice.model_copy(
            update={
                "status": "resolved" if request.action == "continue" else "skipped",
                "selected_ids": selected_ids,
                "updated_at": utc_now(),
            }
        )
        updated = run.model_copy(
            update={
                "choice": updated_choice,
                "metrics": {
                    **run.metrics,
                    "choice_status": updated_choice.status,
                    "choice_selected_ids": selected_ids,
                },
            }
        )
        await self.repository.update_run(updated)
        await self._publish_choice_event(tenant_id, updated, EventType.CHOICE_RESOLVED)
        return updated

    async def approve_plan(
        self,
        tenant_id: str,
        run_id: str,
        expected_version: int,
    ) -> RunRecord:
        plan_run = await self.repository.get_run(tenant_id, run_id)
        if plan_run is None:
            raise LookupError(f"run not found: {run_id}")
        if plan_run.status is not RunStatus.SUCCEEDED or plan_run.plan is None:
            raise ValueError("plan run is not ready for approval")
        if plan_run.plan.status not in {PlanStatus.PROPOSED, PlanStatus.NEEDS_REVISION}:
            raise ValueError("plan is no longer awaiting approval")
        if plan_run.plan.version != expected_version:
            raise ValueError("plan version conflict")

        executing_plan = plan_run.plan.model_copy(
            update={
                "status": PlanStatus.EXECUTING,
                "steps": [step.model_copy(update={"status": PlanStepStatus.APPROVED}) for step in plan_run.plan.steps],
                "updated_at": utc_now(),
            }
        )
        prepared_plan_run = plan_run.model_copy(
            update={
                "plan": executing_plan,
                "metrics": {**plan_run.metrics, "plan_status": executing_plan.status.value},
            }
        )
        await self.repository.update_run(prepared_plan_run)

        request = RunRequest(
            agent_id=plan_run.agent_id,
            agent_revision=plan_run.agent_revision or int(plan_run.metrics.get("root_revision", 0)) or None,
            input=plan_run.input,
            session_id=plan_run.session_id,
            thinking_mode=str(plan_run.metrics.get("thinking_mode", "auto")),
            execution_mode=ExecutionMode.EXECUTE,
            metadata={
                "source_plan_id": executing_plan.plan_id,
                "source_plan_run_id": plan_run.id,
                "source_plan_version": executing_plan.version,
            },
        )
        try:
            execution_run = await self.start(tenant_id, request)
        except Exception:
            restored = plan_run.model_copy(
                update={
                    "plan": plan_run.plan,
                    "metrics": {**plan_run.metrics, "plan_status": plan_run.plan.status.value},
                }
            )
            await self.repository.update_run(restored)
            raise
        await self._publish_plan_event(
            tenant_id,
            prepared_plan_run,
            EventType.PLAN_APPROVED,
            executing_plan,
            execution_run_id=execution_run.id,
        )
        await self._publish_plan_event(
            tenant_id,
            prepared_plan_run,
            EventType.PLAN_EXECUTION_STARTED,
            executing_plan,
            execution_run_id=execution_run.id,
        )
        return execution_run

    async def _drive(
        self,
        run: RunRecord,
        spec: AgentSpec,
    ) -> None:
        async def execute() -> None:
            running = run.model_copy(
                update={
                    "status": RunStatus.RUNNING,
                    "started_at": utc_now(),
                    "metrics": {
                        **run.metrics,
                        "run_span_id": f"span_{run.id}_run",
                    },
                }
            )
            if running.todo is not None:
                running_todo = mark_todo_running(running.todo)
                running = running.model_copy(
                    update={
                        "todo": running_todo,
                        "metrics": {
                            **running.metrics,
                            "todo_status": running_todo.status.value,
                        },
                    }
                )
            await self.repository.update_run(running)
            trace_id = str(running.metrics.get("trace_id") or f"trace_{run.id}")
            run_span_id = str(running.metrics.get("run_span_id") or f"span_{run.id}_run")
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_STARTED,
                    agent_id=spec.id,
                    payload={
                        "agent_revision": spec.revision,
                        "session_id": run.session_id,
                        "thinking_mode": running.metrics.get("thinking_mode", "auto"),
                        "execution_mode": running.metrics.get("execution_mode", "execute"),
                    },
                    trace_id=trace_id,
                    span_id=run_span_id,
                ),
            )
            if running.todo is not None:
                await self._publish_todo_event(
                    run.tenant_id,
                    running,
                    EventType.TODO_CREATED,
                    running.todo,
                )
                await self._publish_todo_event(
                    run.tenant_id,
                    running,
                    EventType.TODO_UPDATED,
                    running.todo,
                )
            output, metrics = await asyncio.wait_for(
                self.runtime.execute(running, spec),
                timeout=spec.policy.timeout_seconds,
            )
            public_output, choice = (
                extract_choice_prompt(output=output, run_id=running.id)
                if running.metrics.get("execution_mode") == ExecutionMode.EXECUTE.value
                else (output, None)
            )
            completed_todo = (
                mark_todo_terminal(running.todo, TodoStatus.COMPLETED)
                if running.todo is not None
                else None
            )
            completed = running.model_copy(
                update={
                    "status": RunStatus.SUCCEEDED,
                    "output": public_output,
                    "choice": choice,
                    "todo": completed_todo,
                    "metrics": {
                        **running.metrics,
                        **metrics,
                        **({
                            "todo_status": completed_todo.status.value,
                            "choice_id": choice.prompt_id,
                            "choice_status": choice.status,
                        } if completed_todo is not None and choice is not None else {
                            **({"todo_status": completed_todo.status.value} if completed_todo is not None else {}),
                            **({"choice_id": choice.prompt_id, "choice_status": choice.status} if choice is not None else {}),
                        }),
                    },
                    "finished_at": utc_now(),
                }
            )
            if running.metrics.get("execution_mode") == ExecutionMode.PLAN.value:
                plan = build_execution_plan(
                    run_id=running.id,
                    session_id=running.session_id,
                    input_text=running.input,
                    output=public_output,
                )
                completed = completed.model_copy(
                    update={
                        "plan": plan,
                        "metrics": {
                            **completed.metrics,
                            "plan_id": plan.plan_id,
                            "plan_version": plan.version,
                            "plan_status": plan.status.value,
                        },
                    }
                )
            await self.repository.update_run(completed)
            if completed.todo is not None:
                await self._publish_todo_event(
                    run.tenant_id,
                    completed,
                    EventType.TODO_COMPLETED,
                    completed.todo,
                )
            if completed.choice is not None:
                await self._publish_choice_event(run.tenant_id, completed, EventType.CHOICE_PROMPTED)
            if completed.plan is not None:
                await self._publish_plan_event(
                    run.tenant_id,
                    completed,
                    EventType.PLAN_PROPOSED,
                    completed.plan,
                )
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_COMPLETED,
                    agent_id=spec.id,
                    payload={
                        "output": public_output,
                        "metrics": completed.metrics,
                        **({"todo": completed.todo.model_dump(mode="json")} if completed.todo else {}),
                        **({"choice": completed.choice.model_dump(mode="json")} if completed.choice else {}),
                        **({"plan": completed.plan.model_dump(mode="json")} if completed.plan else {}),
                    },
                    trace_id=trace_id,
                    span_id=run_span_id,
                ),
            )
            await self._sync_source_plan(completed, PlanStatus.COMPLETED)

        try:
            await execute()
        except asyncio.CancelledError:
            current = await self.repository.get_run(run.tenant_id, run.id)
            base = current or run
            cancelled_todo = (
                mark_todo_terminal(base.todo, TodoStatus.SKIPPED)
                if base.todo is not None
                else None
            )
            cancelled = base.model_copy(
                update={
                    "status": RunStatus.CANCELLED,
                    "todo": cancelled_todo,
                    "metrics": {**base.metrics, **({"todo_status": cancelled_todo.status.value} if cancelled_todo else {})},
                    "finished_at": utc_now(),
                }
            )
            await self.repository.update_run(cancelled)
            if cancelled.todo is not None:
                await self._publish_todo_event(run.tenant_id, cancelled, EventType.TODO_FAILED, cancelled.todo)
            await self._sync_source_plan(cancelled, PlanStatus.CANCELLED)
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_CANCELLED,
                    agent_id=spec.id,
                    payload={"reason": "cancelled by caller"},
                    trace_id=str((current or run).metrics.get("trace_id") or f"trace_{run.id}"),
                    span_id=str((current or run).metrics.get("run_span_id") or f"span_{run.id}_run"),
                ),
            )
        except Exception as exc:
            current = await self.repository.get_run(run.tenant_id, run.id)
            base = current or run
            failed_todo = (
                mark_todo_terminal(base.todo, TodoStatus.FAILED)
                if base.todo is not None
                else None
            )
            failed = base.model_copy(
                update={
                    "status": RunStatus.FAILED,
                    "error": str(exc),
                    "todo": failed_todo,
                    "metrics": {**base.metrics, **({"todo_status": failed_todo.status.value} if failed_todo else {})},
                    "finished_at": utc_now(),
                }
            )
            await self.repository.update_run(failed)
            if failed.todo is not None:
                await self._publish_todo_event(run.tenant_id, failed, EventType.TODO_FAILED, failed.todo)
            await self._sync_source_plan(failed, PlanStatus.FAILED)
            await self.events.publish(
                run.tenant_id,
                RunEvent(
                    run_id=run.id,
                    type=EventType.RUN_FAILED,
                    agent_id=spec.id,
                    payload={"error": str(exc), "error_type": type(exc).__name__},
                    trace_id=str((current or run).metrics.get("trace_id") or f"trace_{run.id}"),
                    span_id=str((current or run).metrics.get("run_span_id") or f"span_{run.id}_run"),
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
