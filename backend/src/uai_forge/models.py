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
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("config", "metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


class ModelConfigWrite(StrictModel):
    id: Optional[str] = None
    name: str = Field(min_length=2, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    secret: Optional[str] = Field(default=None, min_length=1, max_length=20_000)
    base_url: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("config", "metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)


class ModelConfigPatch(StrictModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=80)
    model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    secret: Optional[str] = Field(default=None, min_length=1, max_length=20_000)
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None

    @field_validator("config", "metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return reject_inline_secrets(value) if value is not None else value


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
    max_concurrency: int = Field(default=2, ge=1, le=64)
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
    max_steps: int = Field(default=8, ge=1, le=128)
    max_depth: int = Field(default=4, ge=0, le=16)
    max_tool_calls: int = Field(default=24, ge=0, le=1024)
    max_parallel_children: int = Field(default=4, ge=1, le=128)
    timeout_seconds: float = Field(default=120.0, gt=0, le=3600)
    token_budget: int = Field(default=32_000, ge=1)
    fail_fast: bool = True


class InstanceExecutionPolicyOverrides(StrictModel):
    """The only execution-policy leaves an Instance may tighten in 0.1.x."""

    max_steps: Optional[int] = Field(default=None, ge=1, le=128, strict=True)
    max_depth: Optional[int] = Field(default=None, ge=0, le=16, strict=True)
    max_tool_calls: Optional[int] = Field(default=None, ge=0, le=1024, strict=True)
    max_parallel_children: Optional[int] = Field(
        default=None,
        ge=1,
        le=128,
        strict=True,
    )
    timeout_seconds: Optional[float] = Field(
        default=None,
        gt=0,
        le=3600,
        strict=True,
    )
    token_budget: Optional[int] = Field(default=None, ge=1, strict=True)
    fail_fast: Optional[bool] = Field(default=None, strict=True)


class InstanceConfigOverrides(StrictModel):
    """Fail-closed allowlist for non-secret per-Instance configuration."""

    policy: Optional[InstanceExecutionPolicyOverrides] = None

    @model_serializer
    def serialize_without_empty_defaults(self):
        # Preserve the historical `{}` representation for an Instance that has
        # no overrides while still exposing a concrete OpenAPI/JSON schema.
        if self.policy is None:
            return {}
        return {"policy": self.policy.model_dump(exclude_none=True)}


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


_RESTRICTABLE_POLICY_FIELDS = (
    "max_steps",
    "max_depth",
    "max_tool_calls",
    "max_parallel_children",
    "timeout_seconds",
    "token_budget",
)


def build_effective_agent_spec(
    definition: AgentSpec,
    overrides: InstanceConfigOverrides,
) -> AgentSpec:
    """Build a validated per-Run view without mutating the stored revision."""

    candidate = definition.model_dump(mode="python")
    effective_policy = definition.policy.model_dump(mode="python")
    requested = overrides.policy
    if requested is not None:
        for field_name in _RESTRICTABLE_POLICY_FIELDS:
            override_value = getattr(requested, field_name)
            if override_value is not None:
                effective_policy[field_name] = min(
                    effective_policy[field_name],
                    override_value,
                )
        if requested.fail_fast is not None:
            # `True` is the stricter behavior: a child/tool failure aborts the
            # current frame instead of being converted into an error result.
            effective_policy["fail_fast"] = (
                effective_policy["fail_fast"] or requested.fail_fast
            )
    candidate["policy"] = effective_policy
    return AgentSpec.model_validate(candidate)


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


class InstanceStatus(str, Enum):
    STOPPED = "stopped"
    READY = "ready"
    DEGRADED = "degraded"


class AgentInstance(StrictModel):
    id: str = Field(default_factory=lambda: new_id("ins"))
    tenant_id: str = "default"
    name: str = Field(min_length=2, max_length=80)
    agent_id: str
    agent_revision: Optional[int] = None
    environment: str = "local"
    status: InstanceStatus = InstanceStatus.READY
    max_concurrency: int = Field(default=4, ge=1, le=256)
    config_overrides: InstanceConfigOverrides = Field(
        default_factory=InstanceConfigOverrides
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("config_overrides", mode="before")
    @classmethod
    def reject_plaintext_credentials(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return reject_inline_secrets(value)
        return value


class InstancePatch(StrictModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    agent_revision: Optional[int] = Field(default=None, ge=1)
    environment: Optional[str] = None
    status: Optional[InstanceStatus] = None
    max_concurrency: Optional[int] = Field(default=None, ge=1, le=256)
    config_overrides: Optional[InstanceConfigOverrides] = None

    @field_validator("config_overrides", mode="before")
    @classmethod
    def reject_plaintext_credentials(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return reject_inline_secrets(value)
        return value


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunRequest(StrictModel):
    agent_id: Optional[str] = None
    instance_id: Optional[str] = None
    input: str = Field(min_length=1, max_length=100_000)
    session_id: str = Field(default_factory=lambda: new_id("ses"))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def reject_plaintext_credentials(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return reject_inline_secrets(value)

    @model_validator(mode="after")
    def choose_target(self) -> "RunRequest":
        if bool(self.agent_id) == bool(self.instance_id):
            raise ValueError("provide exactly one of agent_id or instance_id")
        return self


class RunRecord(StrictModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    tenant_id: str = "default"
    agent_id: str
    instance_id: Optional[str] = None
    session_id: str
    status: RunStatus = RunStatus.QUEUED
    input: str
    output: Optional[str] = None
    error: Optional[str] = None
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
    MODEL_STARTED = "model.started"
    MODEL_COMPLETED = "model.completed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    DELEGATION_STARTED = "delegation.started"
    DELEGATION_COMPLETED = "delegation.completed"
    DELEGATION_FAILED = "delegation.failed"
    PERMISSION_REQUIRED = "permission.required"
    BUDGET_UPDATED = "budget.updated"


class RunEvent(StrictModel):
    run_id: str
    sequence: int = 0
    type: EventType
    timestamp: datetime = Field(default_factory=utc_now)
    agent_id: str
    parent_agent_id: Optional[str] = None
    depth: int = 0
    payload: Dict[str, Any] = Field(default_factory=dict)


class GraphIssue(StrictModel):
    code: str
    message: str
    path: List[str] = Field(default_factory=list)


class GraphValidationResult(StrictModel):
    valid: bool
    nodes: List[str] = Field(default_factory=list)
    edges: List[Dict[str, str]] = Field(default_factory=list)
    issues: List[GraphIssue] = Field(default_factory=list)
