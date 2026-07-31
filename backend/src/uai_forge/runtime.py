"""Asynchronous, guarded multi-agent runtime."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    AgentSpec,
    ChildMount,
    EventType,
    ExecutionPolicy,
    ModelBinding,
    RunEvent,
    RunRecord,
)
from .ports import EventBusPort, ModelMessage, ModelRequest, RepositoryPort, ToolCall
from .registry import PluginRegistry
from .schema_validation import (
    InvalidJsonSchema,
    compile_json_schema,
    first_schema_violation,
)


class RuntimeGuardError(RuntimeError):
    pass


class BudgetExceededError(RuntimeGuardError):
    pass


class PermissionRequiredError(RuntimeGuardError):
    pass


class ToolArgumentsError(RuntimeGuardError):
    """Stable argument contract failure that never includes argument values."""

    def __init__(
        self,
        code: str,
        tool_name: str,
        *,
        path: str = "/",
        keyword: str = "schema",
    ) -> None:
        self.code = code
        self.tool_name = tool_name
        self.path = path
        self.keyword = keyword
        super().__init__(
            f"{code}; tool={tool_name}; path={path}; keyword={keyword}"
        )


@dataclass
class BudgetLedger:
    policy: ExecutionPolicy
    scope: str = "run"
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def consume_step(self) -> None:
        async with self.lock:
            if self.steps >= self.policy.max_steps:
                raise BudgetExceededError(f"{self.scope} step budget exhausted")
            self.steps += 1

    async def consume_tool(self) -> None:
        async with self.lock:
            if self.tool_calls >= self.policy.max_tool_calls:
                raise BudgetExceededError(f"{self.scope} tool-call budget exhausted")
            self.tool_calls += 1

    async def add_tokens(self, amount: int) -> None:
        async with self.lock:
            self.tokens += max(0, amount)
            if self.tokens > self.policy.token_budget:
                raise BudgetExceededError(f"{self.scope} token budget exhausted")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "step_limit": self.policy.max_steps,
            "tool_calls": self.tool_calls,
            "tool_call_limit": self.policy.max_tool_calls,
            "tokens": self.tokens,
            "token_limit": self.policy.token_budget,
            "elapsed_ms": round((time.monotonic() - self.started_monotonic) * 1_000, 2),
        }


@dataclass
class InvocationBudget:
    """Charges one operation against both the root and invocation limits."""

    root: BudgetLedger
    local: BudgetLedger

    async def consume_step(self) -> None:
        if self.local is not self.root:
            await self.local.consume_step()
        await self.root.consume_step()

    async def consume_tool(self) -> None:
        if self.local is not self.root:
            await self.local.consume_tool()
        await self.root.consume_tool()

    async def add_tokens(self, amount: int) -> None:
        local_error: Optional[BudgetExceededError] = None
        root_error: Optional[BudgetExceededError] = None
        if self.local is not self.root:
            try:
                await self.local.add_tokens(amount)
            except BudgetExceededError as exc:
                local_error = exc
        try:
            await self.root.add_tokens(amount)
        except BudgetExceededError as exc:
            root_error = exc
        if local_error is not None:
            raise local_error
        if root_error is not None:
            raise root_error

    def event_snapshot(self) -> Dict[str, Any]:
        return {
            **self.root.snapshot(),
            "local_scope": self.local.scope,
            "local": self.local.snapshot(),
        }


@dataclass
class RootConcurrencyLease:
    """Tracks one transferable slot from the root run's child limit."""

    semaphore: asyncio.Semaphore
    held: bool = False

    async def acquire(self) -> None:
        if self.held:
            return
        await self.semaphore.acquire()
        self.held = True

    def release(self) -> None:
        if not self.held:
            return
        self.held = False
        self.semaphore.release()


class AgentRuntime:
    def __init__(
        self,
        repository: RepositoryPort,
        registry: PluginRegistry,
        event_broker: EventBusPort,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.events = event_broker
        self._mount_semaphores: Dict[
            Tuple[str, str, int, str], asyncio.Semaphore
        ] = {}

    def validate_agent_spec(self, spec: AgentSpec) -> None:
        """Expose the runtime binding gate to run submission."""

        self.registry.validate_agent_spec(spec)

    async def _resolve_model_binding(
        self, tenant_id: str, binding: ModelBinding
    ) -> ModelBinding:
        """Resolve a database profile into a short-lived provider binding.

        The returned object is never persisted.  Its credential is a private
        Pydantic attribute so it cannot enter Agent specs, Run records, events,
        traces or API responses.
        """

        get_profile = getattr(self.repository, "get_model_profile", None)
        resolve_credential = getattr(self.repository, "resolve_credential", None)
        profile_id = binding.profile_id
        if not profile_id:
            get_runtime_config = getattr(self.repository, "get_runtime_config", None)
            if get_runtime_config is not None:
                default = await get_runtime_config(
                    tenant_id, "runtime.default_model_profile_id"
                )
                if default is not None and isinstance(default.value, str):
                    profile_id = default.value
        if not profile_id:
            if binding.provider == "openai_compatible":
                raise RuntimeGuardError(
                    "openai_compatible provider requires a database model profile"
                )
            return binding
        if get_profile is None:
            raise RuntimeGuardError("database-backed model profiles are unavailable")
        profile = await get_profile(tenant_id, profile_id)
        if profile is None or not profile.enabled:
            raise RuntimeGuardError(f"model profile is unavailable: {profile_id}")

        # Profile values are the defaults; an Agent revision may carry
        # non-secret extension overrides that are also persisted in SQLite.
        config = {**profile.config, **binding.config}
        if profile.base_url:
            config.setdefault("base_url", profile.base_url)
        resolved = ModelBinding(
            provider=profile.provider,
            model=profile.model,
            profile_id=profile.id,
            config=config,
        )
        if profile.credential_profile_id:
            if resolve_credential is None:
                raise RuntimeGuardError("database-backed credentials are unavailable")
            secret = await resolve_credential(tenant_id, profile.credential_profile_id)
            if not secret:
                raise RuntimeGuardError("model credential profile is unavailable")
            resolved._runtime_credential = secret
        return resolved

    async def execute(self, run: RunRecord, root_spec: AgentSpec) -> Tuple[str, Dict[str, Any]]:
        ledger = BudgetLedger(root_spec.policy)
        root_semaphore = asyncio.Semaphore(root_spec.policy.max_parallel_children)
        output = await self._execute_agent(
            run=run,
            spec=root_spec,
            input_text=run.input,
            budget=InvocationBudget(root=ledger, local=ledger),
            root_semaphore=root_semaphore,
            root_lease=None,
            depth=0,
            parent_agent_id=None,
            path=[],
            allowed_tool_plugins=None,
            absolute_depth_limit=root_spec.policy.max_depth,
        )
        return output, ledger.snapshot()

    async def _emit(
        self,
        run: RunRecord,
        event_type: EventType,
        agent_id: str,
        depth: int,
        payload: Dict[str, Any] = None,
        parent_agent_id: Optional[str] = None,
    ) -> None:
        await self.events.publish(
            run.tenant_id,
            RunEvent(
                run_id=run.id,
                type=event_type,
                agent_id=agent_id,
                parent_agent_id=parent_agent_id,
                depth=depth,
                payload=payload or {},
            ),
        )

    @staticmethod
    def _delegation_definition(mount: ChildMount) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": f"delegate_{mount.alias}",
                "description": mount.description
                or f"Delegate a bounded task to mounted agent {mount.alias}.",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string", "maxLength": 100_000}},
                    "required": ["input"],
                    "additionalProperties": False,
                },
            },
        }

    @staticmethod
    def _compile_argument_validator(
        tool_name: str,
        schema: Dict[str, Any],
    ) -> Any:
        try:
            return compile_json_schema(schema)
        except InvalidJsonSchema as exc:
            raise ToolArgumentsError(
                "tool.parameters_schema_invalid",
                tool_name,
                path=exc.violation.path,
                keyword=exc.violation.keyword,
            ) from exc

    @staticmethod
    def _validate_arguments(
        tool_name: str,
        validator: Any,
        arguments: Any,
    ) -> None:
        violation = first_schema_violation(validator, arguments)
        if violation is not None:
            raise ToolArgumentsError(
                "tool.arguments_invalid",
                tool_name,
                path=violation.path,
                keyword=violation.keyword,
            )

    @staticmethod
    def _safe_preview(value: Any, limit: int = 2_000) -> Any:
        secret_words = ("secret", "password", "token", "api_key", "authorization")

        def scrub(item: Any) -> Any:
            if isinstance(item, dict):
                return {
                    str(key): ("[REDACTED]" if any(word in str(key).lower() for word in secret_words)
                               else scrub(inner))
                    for key, inner in item.items()
                }
            if isinstance(item, list):
                return [scrub(inner) for inner in item[:50]]
            return item

        cleaned = scrub(value)
        encoded = json.dumps(cleaned, ensure_ascii=False, default=str)
        if len(encoded) > limit:
            return encoded[:limit] + "…"
        return cleaned

    async def _execute_agent(
        self,
        run: RunRecord,
        spec: AgentSpec,
        input_text: str,
        budget: InvocationBudget,
        root_semaphore: asyncio.Semaphore,
        root_lease: Optional[RootConcurrencyLease],
        depth: int,
        parent_agent_id: Optional[str],
        path: List[str],
        allowed_tool_plugins: Optional[Set[str]],
        absolute_depth_limit: int,
    ) -> str:
        # Repositories and historical revisions can bypass the current save
        # boundary. Revalidate every root and mounted child before side effects.
        self.validate_agent_spec(spec)
        if depth > absolute_depth_limit:
            raise RuntimeGuardError(
                f"maximum effective delegation depth {absolute_depth_limit} exceeded"
            )
        if spec.id in path:
            raise RuntimeGuardError(
                f"dynamic delegation loop blocked: {' -> '.join(path + [spec.id])}"
            )
        if not spec.enabled:
            raise RuntimeGuardError(f"agent is disabled: {spec.id}")

        await self._emit(
            run,
            EventType.AGENT_STARTED,
            spec.id,
            depth,
            {"name": spec.name, "revision": spec.revision},
            parent_agent_id,
        )
        try:
            memory = (
                self.registry.create_memory(spec.memory)
                if spec.memory.enabled
                else None
            )
            history = [
                ModelMessage(role="system", content=spec.system_prompt),
                *(
                    await memory.load(run.tenant_id, run.session_id, spec.id)
                    if memory is not None
                    else []
                ),
                ModelMessage(role="user", content=input_text),
            ]
            model_binding = await self._resolve_model_binding(run.tenant_id, spec.model)
            provider = self.registry.create_provider(model_binding)
            middlewares = self.registry.create_middlewares(spec.middlewares)
            configured_tool_bindings = {
                binding.exposed_name: binding
                for binding in spec.tools
                if binding.enabled
            }
            tool_bindings = {
                name: binding
                for name, binding in configured_tool_bindings.items()
                if (
                    allowed_tool_plugins is None
                    or binding.plugin_id in allowed_tool_plugins
                )
                and binding.permission != "deny"
            }
            tools = {
                name: self.registry.create_tool(binding)
                for name, binding in tool_bindings.items()
            }
            mounts = {mount.alias: mount for mount in spec.children}
            local_child_semaphore = asyncio.Semaphore(
                spec.policy.max_parallel_children
            )
            tool_definitions = [
                tool.definition(exposed_name=name) for name, tool in tools.items()
            ]
            argument_validators = {
                name: self._compile_argument_validator(name, tool.parameters)
                for name, tool in tools.items()
            }
            for mount in mounts.values():
                definition = self._delegation_definition(mount)
                tool_name = definition["function"]["name"]
                tool_definitions.append(definition)
                argument_validators[tool_name] = self._compile_argument_validator(
                    tool_name,
                    definition["function"]["parameters"],
                )

            for local_step in range(spec.policy.max_steps):
                await budget.consume_step()
                request = ModelRequest(
                    model=model_binding.model,
                    messages=history,
                    tools=tool_definitions,
                    metadata={
                        "run_id": run.id,
                        "agent_id": spec.id,
                        "agent_name": spec.name,
                        "instance_id": run.instance_id,
                        "environment": run.metrics.get("environment"),
                        "depth": depth,
                        "local_step": local_step + 1,
                    },
                )
                context = {
                    "tenant_id": run.tenant_id,
                    "run_id": run.id,
                    "session_id": run.session_id,
                    "agent_id": spec.id,
                    "instance_id": run.instance_id,
                    "environment": run.metrics.get("environment"),
                    "depth": depth,
                }
                for middleware in middlewares:
                    request = await middleware.before_model(context, request)
                await self._emit(
                    run,
                    EventType.MODEL_STARTED,
                    spec.id,
                    depth,
                    {
                        "provider": model_binding.provider,
                        "model": model_binding.model,
                        "step": local_step + 1,
                    },
                    parent_agent_id,
                )
                output = await provider.complete(request)
                for middleware in reversed(middlewares):
                    output = await middleware.after_model(context, output)
                try:
                    await budget.add_tokens(output.usage.total_tokens)
                except BudgetExceededError:
                    await self._emit(
                        run,
                        EventType.BUDGET_UPDATED,
                        spec.id,
                        depth,
                        budget.event_snapshot(),
                        parent_agent_id,
                    )
                    raise
                await self._emit(
                    run,
                    EventType.MODEL_COMPLETED,
                    spec.id,
                    depth,
                    {
                        "provider": model_binding.provider,
                        "model": model_binding.model,
                        "tool_calls": len(output.tool_calls),
                        "usage": output.usage.model_dump(),
                    },
                    parent_agent_id,
                )
                await self._emit(
                    run,
                    EventType.BUDGET_UPDATED,
                    spec.id,
                    depth,
                    budget.event_snapshot(),
                    parent_agent_id,
                )

                if not output.tool_calls:
                    final = output.content
                    if memory is not None:
                        await memory.append(
                            run.tenant_id,
                            run.session_id,
                            spec.id,
                            [
                                ModelMessage(role="user", content=input_text),
                                ModelMessage(role="assistant", content=final),
                            ],
                        )
                    await self._emit(
                        run,
                        EventType.AGENT_COMPLETED,
                        spec.id,
                        depth,
                        {"output": self._safe_preview(final)},
                        parent_agent_id,
                    )
                    return final

                history.append(
                    ModelMessage(
                        role="assistant",
                        content=output.content or None,
                        tool_calls=output.tool_calls,
                    )
                )
                executions = [
                    self._execute_tool_call(
                        run=run,
                        spec=spec,
                        call=call,
                        tools=tools,
                        tool_bindings=tool_bindings,
                        configured_tool_bindings=configured_tool_bindings,
                        mounts=mounts,
                        argument_validators=argument_validators,
                        middlewares=middlewares,
                        budget=budget,
                        root_semaphore=root_semaphore,
                        local_child_semaphore=local_child_semaphore,
                        depth=depth,
                        path=path + [spec.id],
                        allowed_tool_plugins=allowed_tool_plugins,
                        absolute_depth_limit=absolute_depth_limit,
                    )
                    for call in output.tool_calls
                ]
                yielded_root_lease = root_lease is not None and root_lease.held
                if yielded_root_lease:
                    root_lease.release()
                try:
                    if spec.policy.fail_fast:
                        execution_tasks = [
                            asyncio.create_task(execution)
                            for execution in executions
                        ]
                        try:
                            results = await asyncio.gather(*execution_tasks)
                        except BaseException:
                            for task in execution_tasks:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(
                                *execution_tasks,
                                return_exceptions=True,
                            )
                            raise
                    else:
                        raw_results = await asyncio.gather(
                            *executions, return_exceptions=True
                        )
                        results = [
                            f"ERROR: {item}" if isinstance(item, Exception) else item
                            for item in raw_results
                        ]
                except BaseException:
                    # The delegating frame no longer owns a root slot. Nested
                    # delegates release their own leases while unwinding.
                    raise
                if yielded_root_lease:
                    await root_lease.acquire()
                for call, result in zip(output.tool_calls, results):
                    history.append(
                        ModelMessage(
                            role="tool",
                            name=call.name,
                            tool_call_id=call.id,
                            content=result,
                        )
                    )
            raise BudgetExceededError(
                f"agent {spec.id} reached local step limit {spec.policy.max_steps}"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._emit(
                run,
                EventType.AGENT_FAILED,
                spec.id,
                depth,
                {"error": str(exc), "error_type": type(exc).__name__},
                parent_agent_id,
            )
            raise

    async def _execute_tool_call(
        self,
        run: RunRecord,
        spec: AgentSpec,
        call: ToolCall,
        tools: Dict[str, Any],
        tool_bindings: Dict[str, Any],
        configured_tool_bindings: Dict[str, Any],
        mounts: Dict[str, ChildMount],
        argument_validators: Dict[str, Any],
        middlewares: List[Any],
        budget: InvocationBudget,
        root_semaphore: asyncio.Semaphore,
        local_child_semaphore: asyncio.Semaphore,
        depth: int,
        path: List[str],
        allowed_tool_plugins: Optional[Set[str]],
        absolute_depth_limit: int,
    ) -> str:
        await budget.consume_tool()
        if call.name.startswith("delegate_"):
            alias = call.name[len("delegate_") :]
            mount = mounts.get(alias)
            if mount is None:
                raise RuntimeGuardError(f"unknown mounted agent alias: {alias}")
            argument_validator = argument_validators.get(call.name)
            if argument_validator is None:
                raise RuntimeGuardError(
                    f"delegation schema unavailable: {call.name}"
                )
            self._validate_arguments(
                call.name,
                argument_validator,
                call.arguments,
            )
            return await self._delegate(
                run,
                spec,
                mount,
                str(call.arguments.get("input", "")),
                budget.root,
                root_semaphore,
                local_child_semaphore,
                depth,
                path,
                allowed_tool_plugins,
                absolute_depth_limit,
            )

        binding = configured_tool_bindings.get(call.name)
        if binding is None:
            raise RuntimeGuardError(f"unknown tool: {call.name}")
        if (
            allowed_tool_plugins is not None
            and binding.plugin_id not in allowed_tool_plugins
        ):
            raise RuntimeGuardError(
                f"tool outside effective mount scope: {binding.plugin_id}"
            )
        if binding.permission == "deny":
            raise RuntimeGuardError(f"tool policy denied: {call.name}")
        tool = tools.get(call.name)
        if tool is None or call.name not in tool_bindings:
            raise RuntimeGuardError(f"tool unavailable: {call.name}")
        argument_validator = argument_validators.get(call.name)
        if argument_validator is None:
            raise RuntimeGuardError(
                f"tool parameter schema unavailable: {call.name}"
            )
        self._validate_arguments(
            call.name,
            argument_validator,
            call.arguments,
        )
        approved_tools: Set[str] = set(run.metrics.get("approved_tools", []))
        if binding.permission == "confirm" and call.name not in approved_tools:
            await self._emit(
                run,
                EventType.PERMISSION_REQUIRED,
                spec.id,
                depth,
                {"tool": call.name, "call_id": call.id},
            )
            raise PermissionRequiredError(f"tool approval required: {call.name}")

        context = {
            "tenant_id": run.tenant_id,
            "run_id": run.id,
            "session_id": run.session_id,
            "agent_id": spec.id,
            "instance_id": run.instance_id,
            "environment": run.metrics.get("environment"),
            "depth": depth,
        }
        arguments = call.arguments
        for middleware in middlewares:
            arguments = await middleware.before_tool(context, call.name, arguments)
        self._validate_arguments(
            call.name,
            argument_validator,
            arguments,
        )
        await self._emit(
            run,
            EventType.TOOL_STARTED,
            spec.id,
            depth,
            {"tool": call.name, "call_id": call.id, "argument_keys": sorted(arguments)},
        )
        try:
            result = await tool.invoke(arguments, context)
            for middleware in reversed(middlewares):
                result = await middleware.after_tool(context, call.name, result)
            await self._emit(
                run,
                EventType.TOOL_COMPLETED,
                spec.id,
                depth,
                {
                    "tool": call.name,
                    "call_id": call.id,
                    "result": self._safe_preview(result),
                },
            )
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            await self._emit(
                run,
                EventType.TOOL_FAILED,
                spec.id,
                depth,
                {"tool": call.name, "call_id": call.id, "error": str(exc)},
            )
            raise

    async def _delegate(
        self,
        run: RunRecord,
        parent: AgentSpec,
        mount: ChildMount,
        child_input: str,
        root_ledger: BudgetLedger,
        root_semaphore: asyncio.Semaphore,
        local_child_semaphore: asyncio.Semaphore,
        depth: int,
        path: List[str],
        inherited_tool_plugins: Optional[Set[str]],
        parent_depth_limit: int,
    ) -> str:
        target = await self.repository.get_agent(
            run.tenant_id,
            mount.agent_id,
            mount.revision,
        )
        if target is None:
            raise RuntimeGuardError(
                f"mounted agent not found: {mount.agent_id}"
                + (f" revision {mount.revision}" if mount.revision else "")
            )
        key = (run.tenant_id, parent.id, parent.revision, mount.alias)
        semaphore = self._mount_semaphores.setdefault(
            key, asyncio.Semaphore(mount.max_concurrency)
        )
        mount_tool_plugins = (
            None if mount.allowed_tools is None else set(mount.allowed_tools)
        )
        if inherited_tool_plugins is None:
            effective_tool_plugins = mount_tool_plugins
        elif mount_tool_plugins is None:
            effective_tool_plugins = set(inherited_tool_plugins)
        else:
            effective_tool_plugins = inherited_tool_plugins.intersection(
                mount_tool_plugins
            )
        rendered_input = mount.input_template.replace("{input}", child_input)
        root_lease = RootConcurrencyLease(root_semaphore)
        child_depth = depth + 1
        child_depth_limit = min(
            parent_depth_limit,
            child_depth + target.policy.max_depth,
        )
        await self._emit(
            run,
            EventType.DELEGATION_STARTED,
            parent.id,
            depth,
            {
                "alias": mount.alias,
                "child_agent_id": target.id,
                "child_revision": target.revision,
                "allowed_tools": (
                    None
                    if effective_tool_plugins is None
                    else sorted(effective_tool_plugins)
                ),
            },
        )

        async def invoke_child() -> str:
            async with local_child_semaphore:
                async with semaphore:
                    await root_lease.acquire()
                    try:
                        return await self._execute_agent(
                            run=run,
                            spec=target,
                            input_text=rendered_input,
                            budget=InvocationBudget(
                                root=root_ledger,
                                local=BudgetLedger(
                                    target.policy,
                                    scope=f"agent {target.id} local",
                                ),
                            ),
                            root_semaphore=root_semaphore,
                            root_lease=root_lease,
                            depth=child_depth,
                            parent_agent_id=parent.id,
                            path=path,
                            allowed_tool_plugins=effective_tool_plugins,
                            absolute_depth_limit=child_depth_limit,
                        )
                    finally:
                        root_lease.release()

        try:
            try:
                result = await asyncio.wait_for(
                    invoke_child(),
                    timeout=target.policy.timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise RuntimeGuardError(
                    f"child agent {target.id} exceeded local timeout "
                    f"{target.policy.timeout_seconds:g}s"
                ) from exc
            await self._emit(
                run,
                EventType.DELEGATION_COMPLETED,
                parent.id,
                depth,
                {
                    "alias": mount.alias,
                    "child_agent_id": target.id,
                    "result": self._safe_preview(result),
                },
            )
            return result
        except Exception as exc:
            await self._emit(
                run,
                EventType.DELEGATION_FAILED,
                parent.id,
                depth,
                {
                    "alias": mount.alias,
                    "child_agent_id": target.id,
                    "error": str(exc),
                },
            )
            raise
