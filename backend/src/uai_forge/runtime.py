"""Asynchronous, guarded multi-agent runtime."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    AgentSpec,
    ChildMount,
    ExecutionMode,
    EventType,
    ExecutionPolicy,
    ModelBinding,
    PluginKind,
    RunEvent,
    RunRecord,
    ThinkingMode,
    ThinkingResolution,
    new_id,
)
from .ports import (
    EventBusPort,
    ModelMessage,
    ModelOutput,
    ModelRequest,
    RepositoryPort,
    TokenUsage,
    ToolCall,
)
from .registry import PluginBindingError, PluginRegistry
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
    _FAST_PATH_LABEL = "weather_missing_location"
    _WEATHER_INTENT = re.compile(
        r"(?:天气|天氣|气温|氣溫|温度|溫度|降雨|下雨|weather|temperature|forecast)",
        re.IGNORECASE,
    )
    _LOCATION_FREE_WORDS = re.compile(
        r"(?:今天|明天|后天|後天|现在|現在|当前|當前|本周|这周|這周|最近|查询|查詢|查看|告诉我|告訴我|帮我|幫我|请问|請問|怎么样|怎麼樣|如何|情况|情況|信息|資訊|预报|預報|一下|好吗|好嗎|呢|吗|嗎|的|weather|temperature|forecast|today|tomorrow|now|please|what(?:'s| is)?|the|in|at|near)",
        re.IGNORECASE,
    )

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

    @classmethod
    def _fast_path_for_input(cls, spec: AgentSpec, input_text: str, depth: int) -> Optional[str]:
        """Return a bounded response for an explicitly declared clarification path.

        Labels are data, not executable policy.  Only this one allowlisted value is
        interpreted, and only on the root frame.  The detector is intentionally
        conservative: uncertain input stays on the normal model path.
        """

        if depth != 0 or spec.labels.get("routing.fast_path") != cls._FAST_PATH_LABEL:
            return None
        if not cls._WEATHER_INTENT.search(input_text):
            return None
        remaining = cls._WEATHER_INTENT.sub(" ", input_text)
        remaining = cls._LOCATION_FREE_WORDS.sub(" ", remaining)
        remaining = re.sub(r"[^\w\u3400-\u9fff]+", " ", remaining, flags=re.UNICODE)
        remaining = re.sub(r"\b\d+(?:\.\d+)?\b", " ", remaining)
        if re.search(r"[\u3400-\u9fffA-Za-z]{2,}", remaining):
            return None
        return "请告诉我你要查询的城市或地区（例如：北京），我就能继续查询天气。"

    async def _resolve_model_binding(
        self, tenant_id: str, binding: ModelBinding
    ) -> ModelBinding:
        """Resolve a tenant ModelConfig into a short-lived provider binding.

        The returned object is never persisted.  Its credential is a private
        Pydantic attribute so it cannot enter Agent specs, Run records, events,
        traces or API responses.
        """

        get_config = getattr(self.repository, "get_model_config", None)
        resolve_secret = getattr(self.repository, "resolve_model_config_secret", None)
        config_id = binding.model_config_id
        if not config_id:
            get_runtime_config = getattr(self.repository, "get_runtime_config", None)
            if get_runtime_config is not None:
                default = await get_runtime_config(
                    tenant_id, "runtime.default_model_config_id"
                )
                if default is not None and isinstance(default.value, str):
                    config_id = default.value
        if not config_id:
            raise RuntimeGuardError("agent requires a database model configuration")
        if get_config is None:
            raise RuntimeGuardError("database-backed model configurations are unavailable")
        model_config = await get_config(tenant_id, config_id)
        if model_config is None or not model_config.enabled:
            raise RuntimeGuardError(f"model configuration is unavailable: {config_id}")

        # ModelConfig values are the defaults; an Agent revision may carry
        # non-secret extension overrides that are also persisted in SQLite.
        config = {**model_config.config, **binding.config}
        if model_config.base_url:
            config.setdefault("base_url", model_config.base_url)
        try:
            self.registry.validate_binding(model_config.provider, PluginKind.PROVIDER, config)
        except PluginBindingError as exc:
            raise RuntimeGuardError("model configuration is invalid") from exc
        resolved = ModelBinding(
            model_config_id=model_config.id,
            config=config,
        )
        resolved._runtime_provider = model_config.provider
        resolved._runtime_protocol = model_config.protocol
        resolved._runtime_model = model_config.model
        if self.registry.manifests(PluginKind.PROVIDER):
            manifest = self.registry.manifest(model_config.provider, PluginKind.PROVIDER)
            if manifest is not None and manifest.credential_required:
                if resolve_secret is None:
                    raise RuntimeGuardError("database-backed model secrets are unavailable")
                secret = await resolve_secret(tenant_id, model_config.id)
                if not secret:
                    raise RuntimeGuardError("model configuration secret is unavailable")
                resolved._runtime_credential = secret
        elif resolve_secret is not None:
            secret = await resolve_secret(tenant_id, model_config.id)
            if not secret:
                raise RuntimeGuardError("model configuration secret is unavailable")
            resolved._runtime_credential = secret
        return resolved

    async def execute(self, run: RunRecord, root_spec: AgentSpec) -> Tuple[str, Dict[str, Any]]:
        ledger = BudgetLedger(root_spec.policy)
        root_semaphore = asyncio.Semaphore(root_spec.policy.max_parallel_children)
        fast_path = self._fast_path_for_input(root_spec, run.input, 0)
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
            parent_span_id=run.metrics.get("run_span_id"),
        )
        metrics = ledger.snapshot()
        if fast_path is not None:
            metrics["fast_path"] = self._FAST_PATH_LABEL
        return output, metrics

    async def _emit(
        self,
        run: RunRecord,
        event_type: EventType,
        agent_id: str,
        depth: int,
        payload: Dict[str, Any] = None,
        parent_agent_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
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
                trace_id=run.metrics.get("trace_id"),
                span_id=span_id,
                parent_span_id=parent_span_id,
            ),
        )

    async def _complete_model(
        self,
        *,
        provider: Any,
        request: ModelRequest,
        run: RunRecord,
        agent_id: str,
        depth: int,
        parent_agent_id: Optional[str],
        span_id: Optional[str],
        parent_span_id: Optional[str],
    ) -> ModelOutput:
        """Collect a provider text stream behind the owned runtime boundary."""

        # Providers own protocol-specific streaming and must aggregate partial
        # tool-call JSON before returning it in the core contract.  Text and
        # tool calls remain separate so the chat projection never sees a
        # function-call fragment as assistant prose.
        manifest = getattr(provider, "manifest", None)
        capabilities = getattr(manifest, "capabilities", ())
        if "streaming" not in capabilities:
            return await provider.complete(request)

        parts: List[str] = []
        tool_calls: List[ToolCall] = []
        usage: Optional[TokenUsage] = None
        try:
            async for chunk in provider.stream(request):
                if chunk.text:
                    parts.append(chunk.text)
                    await self._emit(
                        run,
                        EventType.MODEL_DELTA,
                        agent_id,
                        depth,
                        {"text": chunk.text},
                        parent_agent_id,
                        span_id,
                        parent_span_id,
                    )
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)
                if chunk.usage is not None:
                    usage = self._merge_usage(usage, chunk.usage)
        except Exception:
            # A stream can be retried only before any public output was exposed.
            # Completed tool calls are private until the model response returns,
            # so a tool-only transport failure can still safely use complete().
            if parts or tool_calls:
                raise
            return await provider.complete(request)

        content = "".join(parts)
        if usage is None:
            usage = TokenUsage(output_tokens=max(0, len(content) // 4))
        elif usage.total_tokens == 0:
            usage = usage.model_copy(
                update={"output_tokens": max(0, len(content) // 4)}
            )
        return ModelOutput(content=content, tool_calls=tool_calls, usage=usage)

    @staticmethod
    def _merge_usage(
        current: Optional[TokenUsage],
        incoming: TokenUsage,
    ) -> TokenUsage:
        """Merge partial stream usage without losing cache dimensions."""

        if current is None:
            return incoming
        return TokenUsage(
            input_tokens=incoming.input_tokens or current.input_tokens,
            output_tokens=incoming.output_tokens or current.output_tokens,
            cached_input_tokens=(
                incoming.cached_input_tokens
                if incoming.cached_input_tokens is not None
                else current.cached_input_tokens
            ),
            cache_creation_input_tokens=(
                incoming.cache_creation_input_tokens
                if incoming.cache_creation_input_tokens is not None
                else current.cache_creation_input_tokens
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

    @staticmethod
    def _thinking_mode_for_run(run: RunRecord) -> ThinkingMode:
        raw = run.metrics.get("thinking_mode", ThinkingMode.AUTO.value)
        try:
            return ThinkingMode(str(raw))
        except ValueError:
            # Historical/custom Run records remain executable with the safe
            # native default instead of failing because of an unknown hint.
            return ThinkingMode.AUTO

    @staticmethod
    def _thinking_resolution_for_provider(
        provider: Any,
        request: ModelRequest,
    ) -> ThinkingResolution:
        resolver = getattr(provider, "thinking_resolution", None)
        if callable(resolver):
            return resolver(request)
        return (
            ThinkingResolution.AUTO
            if request.thinking_mode is ThinkingMode.AUTO
            else ThinkingResolution.UNSUPPORTED
        )

    @staticmethod
    def _execution_mode_for_run(run: RunRecord) -> ExecutionMode:
        raw = run.metrics.get("execution_mode", ExecutionMode.EXECUTE.value)
        try:
            return ExecutionMode(str(raw))
        except ValueError:
            return ExecutionMode.EXECUTE

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
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
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

        span_id = span_id or new_id("span")
        operation_started = time.monotonic()
        thinking_mode = self._thinking_mode_for_run(run)
        execution_mode = self._execution_mode_for_run(run)

        await self._emit(
            run,
            EventType.AGENT_STARTED,
            spec.id,
            depth,
            {"name": spec.name, "revision": spec.revision},
            parent_agent_id,
            span_id,
            parent_span_id,
        )
        await self._emit(
            run,
            EventType.AGENT_PROGRESS,
            spec.id,
            depth,
            {
                "phase": "preparing",
                "status": "active",
                "message": "正在准备上下文",
                "public": True,
            },
            parent_agent_id,
            span_id,
            parent_span_id,
        )
        try:
            fast_path = self._fast_path_for_input(spec, input_text, depth)
            if fast_path is not None:
                await self._emit(
                    run,
                    EventType.AGENT_PROGRESS,
                    spec.id,
                    depth,
                    {
                        "phase": "preflight",
                        "status": "active",
                        "message": "已识别为缺少地点的天气请求，跳过模型链路",
                        "fast_path": self._FAST_PATH_LABEL,
                        "public": True,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                await self._emit(
                    run,
                    EventType.AGENT_PROGRESS,
                    spec.id,
                    depth,
                    {
                        "phase": "clarifying",
                        "status": "complete",
                        "message": "先补充城市或地区，再继续查询",
                        "fast_path": self._FAST_PATH_LABEL,
                        "public": True,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                await self._emit(
                    run,
                    EventType.AGENT_COMPLETED,
                    spec.id,
                    depth,
                    {
                        "output": self._safe_preview(fast_path),
                        "duration_ms": round((time.monotonic() - operation_started) * 1_000, 2),
                        "fast_path": self._FAST_PATH_LABEL,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                await self._emit(
                    run,
                    EventType.AGENT_PROGRESS,
                    spec.id,
                    depth,
                    {
                        "phase": "completed",
                        "status": "complete",
                        "message": "已完成",
                        "public": True,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                return fast_path
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
            if execution_mode is ExecutionMode.PLAN:
                history.insert(
                    -1,
                    ModelMessage(
                        role="system",
                        content=(
                            "当前是计划模式：先研究当前已提供的上下文并生成可审阅的执行计划；"
                            "不调用工具、不委派子 Agent，也不执行外部副作用。不要输出隐藏思考或"
                            "逐步推理，只输出用户可以修改和批准的计划。请尽量使用以下公开结构："
                            "\n# 计划标题\n## 目标\n...\n## 假设\n- ...\n"
                            "## 步骤\n1. ...\n2. ...\n## 风险\n- ...\n"
                            "如果缺少仓库或外部事实，明确写入假设和风险，不要伪造已完成的调查。"
                        ),
                    ),
                )
            else:
                history.insert(
                    -1,
                    ModelMessage(
                        role="system",
                        content=(
                            "当任务确实需要用户在有限选项中做决定时，可以在公开答复末尾追加一个安全选择标记，"
                            "格式必须是单行 HTML 注释：<!-- uai-choice:{\"title\":\"...\",\"description\":\"...\","
                            "\"selection_type\":\"single\",\"required\":false,\"options\":[{\"id\":\"a\","
                            "\"label\":\"选项 A\",\"description\":\"...\",\"recommended\":true},{\"id\":\"b\","
                            "\"label\":\"选项 B\",\"description\":\"...\"}]} -->。"
                            "只在需要明确用户选择时使用，不要把隐藏思考、凭据、原始工具参数或大段 JSON 放进标记。"
                        ),
                    ),
                )
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
            tools = (
                {
                    name: self.registry.create_tool(binding)
                    for name, binding in tool_bindings.items()
                }
                if execution_mode is ExecutionMode.EXECUTE
                else {}
            )
            mounts = (
                {mount.alias: mount for mount in spec.children}
                if execution_mode is ExecutionMode.EXECUTE
                else {}
            )
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
                    thinking_mode=thinking_mode,
                    metadata={
                        "run_id": run.id,
                        "agent_id": spec.id,
                        "agent_name": spec.name,
                        "agent_revision": spec.revision,
                        "depth": depth,
                        "local_step": local_step + 1,
                        "execution_mode": execution_mode.value,
                    },
                )
                context = {
                    "tenant_id": run.tenant_id,
                    "run_id": run.id,
                    "session_id": run.session_id,
                    "agent_id": spec.id,
                    "agent_revision": spec.revision,
                    "depth": depth,
                }
                for middleware in middlewares:
                    request = await middleware.before_model(context, request)
                thinking_resolution = self._thinking_resolution_for_provider(provider, request)
                await self._emit(
                    run,
                    EventType.MODEL_STARTED,
                    spec.id,
                    depth,
                    {
                        "provider": model_binding.provider,
                        "model": model_binding.model,
                        "thinking_mode": thinking_mode.value,
                        "thinking_resolution": thinking_resolution.value,
                        "execution_mode": execution_mode.value,
                        "step": local_step + 1,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                await self._emit(
                    run,
                    EventType.AGENT_PROGRESS,
                    spec.id,
                    depth,
                    {
                        "phase": "analyzing",
                        "status": "active",
                        "message": "正在分析任务",
                        "step": local_step + 1,
                        "public": True,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                if thinking_mode is not ThinkingMode.AUTO:
                    if thinking_resolution.value == "mapped":
                        thinking_message = (
                            "已开启思考模式"
                            if thinking_mode is ThinkingMode.ON
                            else "已关闭思考模式"
                        )
                        thinking_status = "active"
                    elif thinking_resolution.value == "native":
                        thinking_message = "当前模型使用原生思考能力"
                        thinking_status = "active"
                    else:
                        thinking_message = "当前模型未声明可控思考参数，已按模型默认行为运行"
                        thinking_status = "degraded"
                    await self._emit(
                        run,
                        EventType.AGENT_PROGRESS,
                        spec.id,
                        depth,
                        {
                            "phase": "thinking_mode",
                            "status": thinking_status,
                            "message": thinking_message,
                            "thinking_mode": thinking_mode.value,
                            "thinking_resolution": thinking_resolution.value,
                            "public": True,
                        },
                        parent_agent_id,
                        span_id,
                        parent_span_id,
                    )
                if execution_mode is ExecutionMode.PLAN:
                    await self._emit(
                        run,
                        EventType.AGENT_PROGRESS,
                        spec.id,
                        depth,
                        {
                            "phase": "plan",
                            "status": "active",
                            "message": "计划模式：只生成计划，不调用工具或子 Agent",
                            "execution_mode": execution_mode.value,
                            "public": True,
                        },
                        parent_agent_id,
                        span_id,
                        parent_span_id,
                    )
                model_started = time.monotonic()
                try:
                    output = await self._complete_model(
                        provider=provider,
                        request=request,
                        run=run,
                        agent_id=spec.id,
                        depth=depth,
                        parent_agent_id=parent_agent_id,
                        span_id=span_id,
                        parent_span_id=parent_span_id,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self._emit(
                        run,
                        EventType.MODEL_FAILED,
                        spec.id,
                        depth,
                        {
                            "provider": model_binding.provider,
                            "model": model_binding.model,
                            "step": local_step + 1,
                            "duration_ms": round((time.monotonic() - model_started) * 1_000, 2),
                            "error_type": type(exc).__name__,
                        },
                        parent_agent_id,
                        span_id,
                        parent_span_id,
                    )
                    raise
                for middleware in reversed(middlewares):
                    output = await middleware.after_model(context, output)
                if execution_mode is ExecutionMode.PLAN and output.tool_calls:
                    await self._emit(
                        run,
                        EventType.AGENT_PROGRESS,
                        spec.id,
                        depth,
                        {
                            "phase": "plan",
                            "status": "degraded",
                            "message": "计划模式已阻止模型工具调用",
                            "blocked_tool_calls": len(output.tool_calls),
                            "execution_mode": execution_mode.value,
                            "public": True,
                        },
                        parent_agent_id,
                        span_id,
                        parent_span_id,
                    )
                    output = ModelOutput(content=output.content, usage=output.usage)
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
                        span_id,
                        parent_span_id,
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
                        "step": local_step + 1,
                        "tool_calls": len(output.tool_calls),
                        "usage": output.usage.model_dump(),
                        "duration_ms": round((time.monotonic() - model_started) * 1_000, 2),
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                await self._emit(
                    run,
                    EventType.AGENT_PROGRESS,
                    spec.id,
                    depth,
                    {
                        "phase": "tool_call" if output.tool_calls else "composing",
                        "status": "active",
                        "message": "正在调用工具" if output.tool_calls else "正在整理回复",
                        "count": len(output.tool_calls),
                        "public": True,
                    },
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )
                await self._emit(
                    run,
                    EventType.BUDGET_UPDATED,
                    spec.id,
                    depth,
                    budget.event_snapshot(),
                    parent_agent_id,
                    span_id,
                    parent_span_id,
                )

                if not output.tool_calls:
                    final = output.content
                    # A plan is review-only: do not persist it into agent memory,
                    # so selecting plan mode cannot mutate later execution context.
                    if memory is not None and execution_mode is ExecutionMode.EXECUTE:
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
                        {
                            "output": self._safe_preview(final),
                            "duration_ms": round(
                                (time.monotonic() - operation_started) * 1_000,
                                2,
                            ),
                        },
                        parent_agent_id,
                        span_id,
                        parent_span_id,
                    )
                    await self._emit(
                        run,
                        EventType.AGENT_PROGRESS,
                        spec.id,
                        depth,
                        {
                            "phase": "completed",
                            "status": "complete",
                            "message": "已完成",
                            "public": True,
                        },
                        parent_agent_id,
                        span_id,
                        parent_span_id,
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
                        span_id=span_id,
                        parent_span_id=parent_span_id,
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
                {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "duration_ms": round(
                        (time.monotonic() - operation_started) * 1_000,
                        2,
                    ),
                },
                parent_agent_id,
                span_id,
                parent_span_id,
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
        span_id: Optional[str],
        parent_span_id: Optional[str],
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
            await self._emit(
                run,
                EventType.AGENT_PROGRESS,
                spec.id,
                depth,
                {
                    "phase": "delegating",
                    "status": "active",
                    "message": f"正在委派给子 Agent：{alias}",
                    "alias": alias,
                    "public": True,
                },
                span_id=span_id,
                parent_span_id=parent_span_id,
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
                span_id,
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
                span_id=span_id,
                parent_span_id=parent_span_id,
            )
            raise PermissionRequiredError(f"tool approval required: {call.name}")

        context = {
            "tenant_id": run.tenant_id,
            "run_id": run.id,
            "session_id": run.session_id,
            "agent_id": spec.id,
            "agent_revision": spec.revision,
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
        tool_started = time.monotonic()
        await self._emit(
            run,
            EventType.TOOL_STARTED,
            spec.id,
            depth,
            {"tool": call.name, "call_id": call.id, "argument_keys": sorted(arguments)},
            span_id,
            parent_span_id,
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
                    "duration_ms": round(
                        (time.monotonic() - tool_started) * 1_000,
                        2,
                    ),
                },
                span_id,
                parent_span_id,
            )
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            await self._emit(
                run,
                EventType.TOOL_FAILED,
                spec.id,
                depth,
                {
                    "tool": call.name,
                    "call_id": call.id,
                    "error": str(exc),
                    "duration_ms": round(
                        (time.monotonic() - tool_started) * 1_000,
                        2,
                    ),
                },
                span_id,
                parent_span_id,
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
        parent_agent_span_id: Optional[str],
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
        child_span_id = new_id("span")
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
            span_id=child_span_id,
            parent_span_id=parent_agent_span_id,
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
                            span_id=child_span_id,
                            parent_span_id=parent_agent_span_id,
                        )
                    finally:
                        root_lease.release()

        delegation_started = time.monotonic()
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
                    "duration_ms": round(
                        (time.monotonic() - delegation_started) * 1_000,
                        2,
                    ),
                },
                span_id=child_span_id,
                parent_span_id=parent_agent_span_id,
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
                    "duration_ms": round(
                        (time.monotonic() - delegation_started) * 1_000,
                        2,
                    ),
                },
                span_id=child_span_id,
                parent_span_id=parent_agent_span_id,
            )
            raise
