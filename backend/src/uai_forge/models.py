"""Versioned contracts shared by the runtime, API and plugins."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_serializer,
    model_validator,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


_INLINE_SECRET_KEYS = {
    "api_key",
    "authorization",
    "access_token",
    "refresh_token",
    "auth_token",
    "password",
    "private_key",
    "secret",
    "token",
}


def reject_inline_secrets(value: Dict[str, Any]) -> Dict[str, Any]:
    """Require credential references instead of persistable plaintext config."""

    def inspect(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for raw_key, nested in item.items():
                key = str(raw_key).strip().lower().replace("-", "_")
                is_reference = (
                    key.endswith("_ref")
                    or "secret_ref" in key
                )
                is_sensitive = key in _INLINE_SECRET_KEYS or key.startswith("api_key_") or any(
                    key.endswith(f"_{suffix}") for suffix in _INLINE_SECRET_KEYS
                )
                if is_sensitive and not is_reference and nested not in (None, ""):
                    raise ValueError(
                        f"inline credential at {path}.{raw_key} is forbidden; "
                        "use a *Ref or *SecretRef field"
                    )
                inspect(nested, f"{path}.{raw_key}")
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                inspect(nested, f"{path}[{index}]")

    inspect(value, "config")
    return value


class PluginKind(str, Enum):
    PROVIDER = "provider"
    TOOL = "tool"
    SANDBOX = "sandbox"
    MEMORY = "memory"
    STORAGE = "storage"
    EVENT_BUS = "event_bus"
    SCHEDULER = "scheduler"
    MIDDLEWARE = "middleware"
    UI = "ui"


class ModelCatalogEntry(StrictModel):
    """A provider's curated, non-tenant model recommendation."""

    id: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=300)
    tier: Literal["latest", "popular", "legacy"] = "popular"
    source_url: Optional[str] = None


class PluginManifest(StrictModel):
    id: str
    kind: PluginKind
    display_name: str
    version: str = "0.1.0"
    protocol_version: str = "1.0"
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)
    api_protocol: str = "custom"
    credential_required: bool = False
    model_catalog: List[ModelCatalogEntry] = Field(default_factory=list)
    config_schema: Dict[str, Any] = Field(default_factory=dict)
    homepage: Optional[str] = None
    available: bool = True
    source: Literal["builtin", "entry_point", "remote"] = "builtin"
    connection_check: Literal["none", "local", "remote"] = "none"
    connection_schema_version: str = "1.0"
    ui_hints: Dict[str, Any] = Field(default_factory=dict)
    catalog_version: Optional[str] = None
    catalog_updated_at: Optional[datetime] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", value):
            raise ValueError("plugin id must be a lowercase, namespaced identifier")
        return value


class ModelBinding(StrictModel):
    """Agent-side reference to a tenant ModelConfig.

    Provider/model/secret are deliberately runtime-private. Persisted Agent
    revisions only select a reusable configuration and may carry non-secret
    adapter overrides.
    """

    # A placeholder keeps AgentSpec construction ergonomic for schema-only
    # callers; the control API and runtime still fail closed until a tenant
    # row with this ID exists.
    model_config_id: str = Field(default="default", min_length=1, max_length=120)
    config: Dict[str, Any] = Field(default_factory=dict)
    _runtime_provider: Optional[str] = PrivateAttr(default=None)
    _runtime_protocol: Optional[str] = PrivateAttr(default=None)
    _runtime_model: Optional[str] = PrivateAttr(default=None)
    _runtime_credential: Optional[str] = PrivateAttr(default=None)

    @property
    def provider(self) -> str:
        if not self._runtime_provider:
            raise RuntimeError("model binding provider is unresolved")
        return self._runtime_provider

    @property
    def protocol(self) -> str:
        if not self._runtime_protocol:
            raise RuntimeError("model binding protocol is unresolved")
        return self._runtime_protocol

    @property
    def model(self) -> str:
        if not self._runtime_model:
            raise RuntimeError("model binding model is unresolved")
        return self._runtime_model

    @field_validator("config")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


class ModelConfigVerification(StrictModel):
    status: Literal["never", "passed", "failed"] = "never"
    checked_at: Optional[datetime] = None
    code: Optional[str] = None
    latency_ms: Optional[int] = Field(default=None, ge=0)
    endpoint_summary: Optional[str] = None


class ModelConfig(StrictModel):
    """Tenant-owned reusable model connection with a masked secret view."""

    id: str
    tenant_id: str = "default"
    name: str = Field(min_length=2, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    protocol: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    base_url: Optional[str] = None
    masked_secret: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    version: int = Field(default=1, ge=1)
    lifecycle: Literal["draft", "verified", "enabled", "disabled", "error"] = "enabled"
    verification: "ModelConfigVerification" = Field(default_factory=lambda: ModelConfigVerification())
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("config", "metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)

    @model_validator(mode="after")
    def normalize_lifecycle(self) -> "ModelConfig":
        # ``enabled`` remains an additive compatibility view for 0.1 clients;
        # lifecycle is the source of truth for new writes.
        if not self.enabled and self.lifecycle == "enabled":
            self.lifecycle = "disabled"
        if self.lifecycle in {"draft", "verified"}:
            self.enabled = False
        elif self.lifecycle in {"disabled", "error"}:
            self.enabled = False
        elif self.lifecycle == "enabled":
            self.enabled = True
        elif not self.enabled:
            self.lifecycle = "disabled"
        return self


class ModelConfigWrite(StrictModel):
    id: Optional[str] = None
    name: str = Field(min_length=2, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    secret: Optional[str] = Field(default=None, min_length=1, max_length=20_000)
    secret_action: Optional[Literal["replace", "clear"]] = None
    base_url: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    lifecycle: Optional[Literal["draft", "verified", "enabled", "disabled", "error"]] = None

    @field_validator("config", "metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


class ModelConfigPatch(StrictModel):
    expected_version: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=80)
    model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    secret: Optional[str] = Field(default=None, min_length=1, max_length=20_000)
    secret_action: Literal["keep", "replace", "clear"] = "keep"
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    lifecycle: Optional[Literal["draft", "verified", "enabled", "disabled", "error"]] = None

    @field_validator("config", "metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return reject_inline_secrets(value) if value is not None else value

    @model_validator(mode="after")
    def validate_secret_action(self) -> "ModelConfigPatch":
        if self.secret_action == "replace" and self.secret is None:
            raise ValueError("secret is required when secret_action is replace")
        if self.secret_action != "replace" and self.secret is not None:
            raise ValueError("secret is only accepted with secret_action replace")
        return self


class ModelConnectionCheckRequest(StrictModel):
    provider: str
    protocol: str
    model: str
    base_url: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    credential: Optional[str] = None


class ModelConnectionCheckResult(StrictModel):
    status: Literal["passed", "failed", "partial"]
    code: str
    checked_at: datetime = Field(default_factory=utc_now)
    latency_ms: Optional[int] = Field(default=None, ge=0)
    endpoint_summary: Optional[str] = None
    provider: str
    model: str


class SetupResourceSummary(StrictModel):
    total: int = Field(default=0, ge=0)
    runnable: int = Field(default=0, ge=0)
    verified_enabled: int = Field(default=0, ge=0)
    active: int = Field(default=0, ge=0)
    ready: int = Field(default=0, ge=0)
    blocking_issues: List["ReadinessIssue"] = Field(default_factory=list)
    last_terminal_at: Optional[datetime] = None


class SetupStatus(StrictModel):
    connection: Literal["connected", "unauthorized", "incompatible", "unavailable"]
    model_connections: SetupResourceSummary = Field(default_factory=SetupResourceSummary)
    agents: SetupResourceSummary = Field(default_factory=SetupResourceSummary)
    runs: SetupResourceSummary = Field(default_factory=SetupResourceSummary)
    next_action: Literal[
        "connect",
        "create_model_config",
        "verify_model_config",
        "create_agent",
        "run_agent",
        "none",
    ]


class CapabilityStatus(StrictModel):
    id: str
    state: Literal["implemented", "partial", "planned", "unavailable"]
    summary: str
    limits: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)


class Remediation(StrictModel):
    action: str
    target: Optional[str] = None


class ReadinessIssue(StrictModel):
    code: str
    resource_type: str
    resource_id: Optional[str] = None
    path: Optional[str] = None
    message: str
    remediation: Remediation


class AgentReadiness(StrictModel):
    agent_id: str
    revision: int
    runnable: bool
    issues: List[ReadinessIssue] = Field(default_factory=list)


class ProblemFieldError(StrictModel):
    field: str
    code: str
    message: str


class ProblemResource(StrictModel):
    type: str
    id: Optional[str] = None


class ProblemDetails(StrictModel):
    type: str = "uai-forge.problem/1.0"
    code: str
    message: str
    field_errors: List[ProblemFieldError] = Field(default_factory=list)
    resource: Optional[ProblemResource] = None
    retryable: bool = False
    remediation: Optional[Remediation] = None
    correlation_id: str


class ModelConfigReference(StrictModel):
    agent_id: str
    agent_name: str
    revision: int
    path: str = "model.model_config_id"


class ModelConfigReferences(StrictModel):
    items: List[ModelConfigReference] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    next_cursor: Optional[str] = None


class RuntimeConfigEntry(StrictModel):
    """Versioned, non-secret business configuration from the database."""

    tenant_id: str = "default"
    key: str = Field(min_length=1, max_length=200)
    value: Any = None
    version: int = Field(default=1, ge=1)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("value")
    @classmethod
    def reject_plaintext_credentials(cls, value: Any) -> Any:
        return reject_inline_secrets({"value": value})["value"]


class RuntimeConfigPatch(StrictModel):
    key: str = Field(min_length=1, max_length=200)
    value: Any = None
    expected_version: Optional[int] = Field(default=None, ge=1)

    @field_validator("value")
    @classmethod
    def reject_plaintext_credentials(cls, value: Any) -> Any:
        return reject_inline_secrets({"value": value})["value"]


class ToolBinding(StrictModel):
    plugin_id: str
    alias: Optional[str] = None
    enabled: bool = True
    permission: Literal["auto", "confirm", "deny"] = "auto"
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)

    @property
    def exposed_name(self) -> str:
        return self.alias or self.plugin_id.replace(".", "_").replace("-", "_")


class SandboxBinding(StrictModel):
    """Configuration for an execution-isolation provider.

    Sandbox bindings are deliberately separate from tool bindings. A tool may
    request a sandbox, but the agent does not receive a sandbox merely because
    it has a read-only tool mounted.
    """

    plugin_id: str
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


DEFAULT_AGENT_TOOL_PLUGIN_IDS = (
    "tool.web_search",
    "tool.web_fetch",
    "tool.web_json",
    "tool.web_rss",
    "tool.calculator",
    "tool.utc_now",
)


def default_tool_bindings() -> List[ToolBinding]:
    """Return the safe, read-only tools mounted for a new Agent by default."""

    return [
        ToolBinding(
            plugin_id=plugin_id,
            alias=plugin_id.split(".", 1)[-1].replace("-", "_"),
            permission="auto",
        )
        for plugin_id in DEFAULT_AGENT_TOOL_PLUGIN_IDS
    ]


class MemoryBinding(StrictModel):
    plugin_id: str = "memory.in_process"
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


class MiddlewareBinding(StrictModel):
    plugin_id: str
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


class ChildMount(StrictModel):
    alias: str
    agent_id: str
    description: str = ""
    revision: Optional[int] = None
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description=(
            "Tool plugin IDs permitted in the mounted bounded subtree. "
            "Null inherits the upstream scope; an empty list denies all plugin tools."
        ),
    )
    max_concurrency: int = Field(default=4, ge=1, le=64)
    input_template: str = "{input}"

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", value):
            raise ValueError("mount alias must use lowercase letters, numbers, _ or -")
        return value

    @field_validator("allowed_tools")
    @classmethod
    def validate_allowed_tools(
        cls,
        value: Optional[List[str]],
    ) -> Optional[List[str]]:
        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("mount allowed_tools must not contain duplicates")
        for plugin_id in value:
            if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", plugin_id):
                raise ValueError(
                    "mount allowed_tools entries must be lowercase plugin IDs"
                )
        return value


class ExecutionPolicy(StrictModel):
    max_steps: int = Field(default=20, ge=1, le=128)
    max_depth: int = Field(default=6, ge=0, le=16)
    max_tool_calls: int = Field(default=64, ge=0, le=1024)
    max_parallel_children: int = Field(default=6, ge=1, le=128)
    timeout_seconds: float = Field(default=300.0, gt=0, le=3600)
    token_budget: int = Field(default=64_000, ge=1)
    fail_fast: bool = True


class AgentSpec(StrictModel):
    id: str = Field(default_factory=lambda: new_id("agt"))
    tenant_id: str = "default"
    revision: int = Field(default=1, ge=1)
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(min_length=1, max_length=50_000)
    model: ModelBinding = Field(default_factory=ModelBinding)
    tools: List[ToolBinding] = Field(default_factory=list)
    children: List[ChildMount] = Field(default_factory=list)
    memory: MemoryBinding = Field(default_factory=MemoryBinding)
    middlewares: List[MiddlewareBinding] = Field(default_factory=list)
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    labels: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> "AgentSpec":
        aliases = [mount.alias for mount in self.children]
        if len(aliases) != len(set(aliases)):
            raise ValueError("child mount aliases must be unique")
        tool_names = [tool.exposed_name for tool in self.tools if tool.enabled]
        if len(tool_names) != len(set(tool_names)):
            raise ValueError("tool aliases must be unique")
        collisions = set(tool_names).intersection({f"delegate_{alias}" for alias in aliases})
        if collisions:
            raise ValueError(f"tool and child mount names collide: {sorted(collisions)}")
        return self


class AgentRevisionInfo(StrictModel):
    """Administrative view of an immutable Agent snapshot."""

    agent_id: str
    revision: int = Field(ge=1)
    status: Literal["draft", "published"]
    is_latest: bool = False
    spec: AgentSpec
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    published_at: Optional[datetime] = None


class AgentPatch(StrictModel):
    expected_revision: int = Field(ge=1)
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    system_prompt: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    model: Optional[ModelBinding] = None
    tools: Optional[List[ToolBinding]] = None
    children: Optional[List[ChildMount]] = None
    memory: Optional[MemoryBinding] = None
    middlewares: Optional[List[MiddlewareBinding]] = None
    policy: Optional[ExecutionPolicy] = None
    labels: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None


class AgentRollbackRequest(StrictModel):
    """Move the mutable ``latest`` pointer to an immutable revision."""

    revision: int = Field(ge=1)
    expected_revision: int = Field(ge=1)


class AgentPublishRequest(StrictModel):
    """Publish the current latest draft using a compare-and-swap guard."""

    expected_revision: int = Field(ge=1)


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThinkingMode(str, Enum):
    """Provider-neutral request preference; never a chain-of-thought payload."""

    OFF = "off"
    AUTO = "auto"
    ON = "on"


class ThinkingResolution(str, Enum):
    """Safe public outcome of mapping a thinking preference at the provider edge."""

    AUTO = "auto"
    MAPPED = "mapped"
    NATIVE = "native"
    UNSUPPORTED = "unsupported"


class ExecutionMode(str, Enum):
    """Run intent; plan mode never grants execution capabilities."""

    EXECUTE = "execute"
    PLAN = "plan"


class PlanStatus(str, Enum):
    """Public lifecycle of a reviewable plan artifact."""

    PROPOSED = "proposed"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PlanStepStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    scope: List[str] = Field(default_factory=list, max_length=8)
    dependencies: List[str] = Field(default_factory=list, max_length=12)
    risk: Literal["low", "medium", "high"] = "medium"
    status: PlanStepStatus = PlanStepStatus.PROPOSED


class ExecutionPlan(StrictModel):
    """A user-visible plan, separate from hidden model reasoning."""

    plan_id: str = Field(default_factory=lambda: new_id("plan"), min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    version: int = Field(default=1, ge=1)
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=2_000)
    assumptions: List[str] = Field(default_factory=list, max_length=12)
    steps: List[PlanStep] = Field(min_length=1, max_length=24)
    risks: List[str] = Field(default_factory=list, max_length=12)
    status: PlanStatus = PlanStatus.PROPOSED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TodoStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TodoItem(StrictModel):
    """A public task-monitor item, never a transcript of hidden reasoning."""

    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1_000)
    status: TodoStatus = TodoStatus.PENDING


class TaskTodoList(StrictModel):
    """Provider-neutral TodoList for complex execute-mode Runs."""

    todo_id: str = Field(default_factory=lambda: new_id("todo"), min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    title: str = Field(default="任务清单", min_length=1, max_length=200)
    items: List[TodoItem] = Field(min_length=2, max_length=24)
    status: TodoStatus = TodoStatus.PENDING
    source: Literal["automatic", "plan"] = "automatic"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ChoiceOption(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)
    recommended: bool = False


class ChoicePrompt(StrictModel):
    """A safe, explicit user choice emitted as a public interaction artifact."""

    prompt_id: str = Field(default_factory=lambda: new_id("choice"), min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1_000)
    selection_type: Literal["single", "multiple"] = "single"
    options: List[ChoiceOption] = Field(min_length=2, max_length=8)
    required: bool = False
    status: Literal["open", "resolved", "skipped"] = "open"
    selected_ids: List[str] = Field(default_factory=list, max_length=8)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlanEditRequest(StrictModel):
    expected_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=2_000)
    assumptions: List[str] = Field(default_factory=list, max_length=12)
    steps: List[PlanStep] = Field(min_length=1, max_length=24)
    risks: List[str] = Field(default_factory=list, max_length=12)


class PlanApprovalRequest(StrictModel):
    expected_version: int = Field(ge=1)


class ChoiceResolutionRequest(StrictModel):
    action: Literal["continue", "skip"]
    selected_ids: List[str] = Field(default_factory=list, max_length=8)


class RunRequest(StrictModel):
    agent_id: str = Field(min_length=1, max_length=120)
    agent_revision: Optional[int] = Field(default=None, ge=1)
    input: str = Field(min_length=1, max_length=100_000)
    session_id: str = Field(default_factory=lambda: new_id("ses"))
    thinking_mode: ThinkingMode = ThinkingMode.AUTO
    execution_mode: ExecutionMode = ExecutionMode.EXECUTE
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)

class RunRecord(StrictModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    tenant_id: str = "default"
    agent_id: str
    agent_revision: Optional[int] = Field(default=None, ge=1)
    session_id: str
    status: RunStatus = RunStatus.QUEUED
    input: str
    output: Optional[str] = None
    error: Optional[str] = None
    plan: Optional[ExecutionPlan] = None
    todo: Optional[TaskTodoList] = None
    choice: Optional[ChoicePrompt] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class EventType(str, Enum):
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_PROGRESS = "agent.progress"
    MODEL_STARTED = "model.started"
    MODEL_DELTA = "model.delta"
    MODEL_COMPLETED = "model.completed"
    MODEL_FAILED = "model.failed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    DELEGATION_STARTED = "delegation.started"
    DELEGATION_COMPLETED = "delegation.completed"
    DELEGATION_FAILED = "delegation.failed"
    PERMISSION_REQUIRED = "permission.required"
    BUDGET_UPDATED = "budget.updated"
    PLAN_PROPOSED = "plan.proposed"
    PLAN_UPDATED = "plan.updated"
    PLAN_APPROVED = "plan.approved"
    PLAN_EXECUTION_STARTED = "plan.execution_started"
    PLAN_COMPLETED = "plan.completed"
    PLAN_FAILED = "plan.failed"
    PLAN_REJECTED = "plan.rejected"
    PLAN_CANCELLED = "plan.cancelled"
    TODO_CREATED = "todo.created"
    TODO_UPDATED = "todo.updated"
    TODO_COMPLETED = "todo.completed"
    TODO_FAILED = "todo.failed"
    CHOICE_PROMPTED = "choice.prompted"
    CHOICE_RESOLVED = "choice.resolved"


class RunEvent(StrictModel):
    run_id: str
    sequence: int = 0
    type: EventType
    timestamp: datetime = Field(default_factory=utc_now)
    agent_id: str
    parent_agent_id: Optional[str] = None
    depth: int = 0
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Optional trace correlation keeps the v1 event contract compatible with
    # historical events while allowing the runtime to expose a complete
    # parent/child execution chain without leaking provider objects.
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None


class GraphIssue(StrictModel):
    code: str
    message: str
    path: List[str] = Field(default_factory=list)


class GraphValidationResult(StrictModel):
    valid: bool
    nodes: List[str] = Field(default_factory=list)
    edges: List[Dict[str, str]] = Field(default_factory=list)
    issues: List[GraphIssue] = Field(default_factory=list)
