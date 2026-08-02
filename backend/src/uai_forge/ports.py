"""Stable runtime ports implemented by built-ins and third-party plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import Field, field_validator

from .models import (
    AgentSpec,
    ModelConfig,
    ModelConnectionCheckRequest,
    ModelConnectionCheckResult,
    RuntimeConfigEntry,
    ToolCredential,
    PluginManifest,
    RunEvent,
    RunRecord,
    RunRequest,
    ExecutionMode,
    ThinkingMode,
    ThinkingResolution,
    StrictModel,
    SandboxBinding,
)


@runtime_checkable
class RepositoryPort(Protocol):
    """Small persistence surface required by graph validation and Run execution.

    Control-plane CRUD is intentionally not part of this port. Adapters may expose
    richer administrative methods, while the execution core remains coupled only
    to UAI Forge domain contracts.
    """

    async def get_agent(
        self,
        tenant_id: str,
        agent_id: str,
        revision: Optional[int] = None,
    ) -> Optional[AgentSpec]:
        ...

    async def create_run(self, run: RunRecord) -> RunRecord:
        ...

    async def update_run(self, run: RunRecord) -> RunRecord:
        ...

    async def get_run(
        self,
        tenant_id: str,
        run_id: str,
    ) -> Optional[RunRecord]:
        ...


@runtime_checkable
class ConfigurationPort(Protocol):
    """Optional control-plane surface for database-backed model configs."""

    async def get_model_config(
        self, tenant_id: str, config_id: str
    ) -> Optional[ModelConfig]:
        ...

    async def resolve_model_config_secret(
        self, tenant_id: str, config_id: str, *, include_disabled: bool = False
    ) -> Optional[str]:
        ...

    async def get_runtime_config(
        self, tenant_id: str, key: str
    ) -> Optional[RuntimeConfigEntry]:
        ...


@runtime_checkable
class ToolCredentialPort(Protocol):
    """Internal runtime boundary for deployment-managed tool credentials."""

    async def get_tool_credential(
        self, tenant_id: str, credential_id: str
    ) -> Optional[ToolCredential]:
        ...

    async def resolve_tool_credential_secret(
        self,
        tenant_id: str,
        credential_id: str,
        *,
        include_disabled: bool = False,
    ) -> Optional[str]:
        ...


@runtime_checkable
class RunSubmissionPort(Protocol):
    """Application boundary for a tool that starts a follow-up conversation."""

    async def start(self, tenant_id: str, request: RunRequest) -> RunRecord:
        ...


@runtime_checkable
class EventStorePort(Protocol):
    """Durable event operations used by the built-in live event adapter."""

    async def append_event(self, tenant_id: str, event: RunEvent) -> RunEvent:
        ...

    async def list_events(
        self,
        tenant_id: str,
        run_id: str,
        after_sequence: int = 0,
    ) -> List[RunEvent]:
        ...

    async def terminal_event_exists(self, tenant_id: str, run_id: str) -> bool:
        ...


@runtime_checkable
class EventBusPort(Protocol):
    """Core-facing event publication boundary."""

    async def publish(self, tenant_id: str, event: RunEvent) -> RunEvent:
        ...


@runtime_checkable
class EventStreamPort(EventBusPort, Protocol):
    """Optional replay/live subscription surface used by HTTP/SSE adapters."""

    def subscribe(
        self,
        tenant_id: str,
        run_id: str,
        after_sequence: int = 0,
        heartbeat_seconds: float = 15.0,
    ) -> AsyncIterator[Optional[RunEvent]]:
        ...


class ToolCall(StrictModel):
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ModelMessage(StrictModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)


class TokenUsage(StrictModel):
    """Provider-neutral model token accounting.

    Cache counters are input-token subdivisions.  They are intentionally not
    added to ``total_tokens`` because providers such as OpenAI already include
    cached input in their reported prompt total.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: Optional[int] = Field(default=None, ge=0)
    cache_creation_input_tokens: Optional[int] = Field(default=None, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ModelRequest(StrictModel):
    model: str
    messages: List[ModelMessage]
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    thinking_mode: ThinkingMode = ThinkingMode.AUTO
    execution_mode: ExecutionMode = ExecutionMode.EXECUTE
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelOutput(StrictModel):
    content: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw: Dict[str, Any] = Field(default_factory=dict)


class ModelStreamChunk(StrictModel):
    """Provider-neutral increment emitted during a model response.

    Providers must aggregate protocol-specific partial tool-call fragments before
    putting them in ``tool_calls``.  The runtime therefore only sees complete,
    provider-neutral calls and can keep them out of the public text event stream.
    """

    text: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Optional[TokenUsage] = None


class ModelProvider(ABC):
    manifest: PluginManifest

    @abstractmethod
    async def complete(self, request: ModelRequest) -> ModelOutput:
        raise NotImplementedError

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        """Compatibility fallback for providers without native streaming."""

        output = await self.complete(request)
        yield ModelStreamChunk(
            text=output.content,
            tool_calls=output.tool_calls,
            usage=output.usage,
        )

    def thinking_resolution(self, request: ModelRequest) -> ThinkingResolution:
        """Return a safe, provider-neutral mapping outcome for observability."""

        return (
            ThinkingResolution.AUTO
            if request.thinking_mode is ThinkingMode.AUTO
            else ThinkingResolution.UNSUPPORTED
        )

    async def check_connection(
        self,
        request: ModelConnectionCheckRequest,
    ) -> ModelConnectionCheckResult:
        """Optional, low-cost provider preflight with a safe default."""

        return ModelConnectionCheckResult(
            status="partial",
            code="provider.connection_check_unsupported",
            provider=request.provider,
            model=request.model,
        )

    async def check(
        self,
        request: ModelConnectionCheckRequest,
    ) -> ModelConnectionCheckResult:
        """Canonical UAI Forge connection-check entry point.

        ``check_connection`` remains the adapter-facing compatibility hook so
        existing providers can opt in without a breaking change.  The public
        protocol uses this shorter verb and keeps the provider-specific
        implementation behind the owned boundary.
        """

        return await self.check_connection(request)


@runtime_checkable
class ModelConnectionChecker(Protocol):
    """Provider-edge preflight contract owned by UAI Forge."""

    async def check(
        self,
        request: ModelConnectionCheckRequest,
    ) -> ModelConnectionCheckResult:
        ...


class ToolPlugin(ABC):
    manifest: PluginManifest
    name: str
    description: str
    parameters: Dict[str, Any]

    def definition(self, exposed_name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": exposed_name or self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        raise NotImplementedError


class SandboxRequest(StrictModel):
    """Provider-neutral request for one isolated, non-shell process."""

    command: List[str] = Field(min_length=1, max_length=32)
    stdin: str = Field(default="", max_length=1_000_000)
    timeout_seconds: Optional[float] = Field(default=None, gt=0, le=600)
    max_output_bytes: Optional[int] = Field(default=None, ge=1, le=2_000_000)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: List[str]) -> List[str]:
        if any(not item or "\x00" in item for item in value):
            raise ValueError("sandbox.command_invalid")
        return value


class SandboxResult(StrictModel):
    """Bounded public result; raw process handles never cross this port."""

    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    truncated: bool = False
    duration_ms: int = 0


class SandboxProvider(ABC):
    """Execution-isolation port implemented by Docker, VM, WASM, or remote workers."""

    manifest: PluginManifest

    @abstractmethod
    async def execute(
        self,
        request: SandboxRequest,
        context: Dict[str, Any],
    ) -> SandboxResult:
        raise NotImplementedError


class MemoryStore(ABC):
    manifest: PluginManifest

    @abstractmethod
    async def load(self, tenant_id: str, session_id: str, agent_id: str) -> List[ModelMessage]:
        raise NotImplementedError

    @abstractmethod
    async def append(
        self,
        tenant_id: str,
        session_id: str,
        agent_id: str,
        messages: List[ModelMessage],
    ) -> None:
        raise NotImplementedError


class Middleware(ABC):
    """Low-coupling lifecycle hooks. Methods may mutate the supplied values."""

    manifest: PluginManifest

    async def before_model(self, context: Dict[str, Any], request: ModelRequest) -> ModelRequest:
        return request

    async def after_model(self, context: Dict[str, Any], output: ModelOutput) -> ModelOutput:
        return output

    async def before_tool(
        self, context: Dict[str, Any], name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        return arguments

    async def after_tool(self, context: Dict[str, Any], name: str, result: Any) -> Any:
        return result


class Scheduler(ABC):
    manifest: PluginManifest

    @abstractmethod
    async def schedule(self, schedule_id: str, expression: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, schedule_id: str) -> None:
        raise NotImplementedError
