"""Plugin registry with capability discovery and protocol compatibility checks."""

from __future__ import annotations

from importlib import metadata
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import (
    AgentSpec,
    MemoryBinding,
    MiddlewareBinding,
    ModelBinding,
    PluginKind,
    PluginManifest,
    SandboxBinding,
    ToolBinding,
)
from .ports import MemoryStore, Middleware, ModelProvider, SandboxProvider, ToolPlugin
from .schema_validation import (
    InvalidJsonSchema,
    compile_json_schema,
    first_schema_violation,
)

CORE_PROTOCOL_MAJOR = 1

ProviderFactory = Callable[[ModelBinding], ModelProvider]
ToolFactory = Callable[[ToolBinding], ToolPlugin]
MemoryFactory = Callable[[MemoryBinding], MemoryStore]
MiddlewareFactory = Callable[[MiddlewareBinding], Middleware]
SandboxFactory = Callable[[SandboxBinding], SandboxProvider]


class PluginCompatibilityError(ValueError):
    pass


class PluginNotFoundError(LookupError):
    pass


class PluginBindingError(ValueError):
    """Stable, non-secret error raised when a plugin binding is unusable."""

    def __init__(
        self,
        code: str,
        plugin_id: str,
        expected_kind: PluginKind,
        *,
        path: str = "/",
        keyword: Optional[str] = None,
        registered_kinds: Optional[List[str]] = None,
    ) -> None:
        self.code = code
        self.plugin_id = plugin_id
        self.expected_kind = expected_kind
        self.path = path
        self.keyword = keyword
        self.registered_kinds = registered_kinds or []
        components = [
            code,
            f"plugin={plugin_id}",
            f"kind={expected_kind.value}",
        ]
        if path != "/":
            components.append(f"path={path}")
        if keyword:
            components.append(f"keyword={keyword}")
        if self.registered_kinds:
            components.append(f"registered={','.join(self.registered_kinds)}")
        super().__init__("; ".join(components))

    def as_detail(self) -> Dict[str, Any]:
        detail: Dict[str, Any] = {
            "code": self.code,
            "plugin_id": self.plugin_id,
            "expected_kind": self.expected_kind.value,
            "path": self.path,
        }
        if self.keyword:
            detail["keyword"] = self.keyword
        if self.registered_kinds:
            detail["registered_kinds"] = self.registered_kinds
        return detail


class PluginRegistry:
    """One registry per application; no global mutable plugin state."""

    def __init__(self) -> None:
        self._manifests: Dict[Tuple[PluginKind, str], PluginManifest] = {}
        self._config_validators: Dict[Tuple[PluginKind, str], Any] = {}
        self._providers: Dict[str, ProviderFactory] = {}
        self._tools: Dict[str, ToolFactory] = {}
        self._memories: Dict[str, MemoryFactory] = {}
        self._middlewares: Dict[str, MiddlewareFactory] = {}
        self._sandboxes: Dict[str, SandboxFactory] = {}
        self.discovery_errors: List[str] = []

    @staticmethod
    def _assert_compatible(manifest: PluginManifest) -> None:
        try:
            major = int(manifest.protocol_version.split(".", 1)[0])
        except (TypeError, ValueError) as exc:
            raise PluginCompatibilityError(
                f"{manifest.id} has invalid protocol version {manifest.protocol_version}"
            ) from exc
        if major != CORE_PROTOCOL_MAJOR:
            raise PluginCompatibilityError(
                f"{manifest.id} targets protocol {manifest.protocol_version}; "
                f"core requires {CORE_PROTOCOL_MAJOR}.x"
            )

    @staticmethod
    def _compile_config_validator(manifest: PluginManifest) -> Any:
        try:
            return compile_json_schema(manifest.config_schema)
        except InvalidJsonSchema as exc:
            raise PluginBindingError(
                "plugin.schema_invalid",
                manifest.id,
                manifest.kind,
                path=exc.violation.path,
                keyword=exc.violation.keyword,
            ) from exc

    def _register_manifest(self, manifest: PluginManifest) -> None:
        self._assert_compatible(manifest)
        key = (manifest.kind, manifest.id)
        if key in self._manifests:
            raise ValueError(f"plugin already registered: {manifest.kind.value}:{manifest.id}")
        validator = self._compile_config_validator(manifest)
        self._manifests[key] = manifest
        self._config_validators[key] = validator

    def register_provider(self, manifest: PluginManifest, factory: ProviderFactory) -> None:
        if manifest.kind != PluginKind.PROVIDER:
            raise PluginBindingError(
                "plugin.kind_mismatch",
                manifest.id,
                PluginKind.PROVIDER,
                registered_kinds=[manifest.kind.value],
            )
        self._register_manifest(manifest)
        self._providers[manifest.id] = factory

    def register_tool(self, manifest: PluginManifest, factory: ToolFactory) -> None:
        if manifest.kind != PluginKind.TOOL:
            raise PluginBindingError(
                "plugin.kind_mismatch",
                manifest.id,
                PluginKind.TOOL,
                registered_kinds=[manifest.kind.value],
            )
        self._register_manifest(manifest)
        self._tools[manifest.id] = factory

    def register_memory(self, manifest: PluginManifest, factory: MemoryFactory) -> None:
        if manifest.kind != PluginKind.MEMORY:
            raise PluginBindingError(
                "plugin.kind_mismatch",
                manifest.id,
                PluginKind.MEMORY,
                registered_kinds=[manifest.kind.value],
            )
        self._register_manifest(manifest)
        self._memories[manifest.id] = factory

    def register_middleware(self, manifest: PluginManifest, factory: MiddlewareFactory) -> None:
        if manifest.kind != PluginKind.MIDDLEWARE:
            raise PluginBindingError(
                "plugin.kind_mismatch",
                manifest.id,
                PluginKind.MIDDLEWARE,
                registered_kinds=[manifest.kind.value],
            )
        self._register_manifest(manifest)
        self._middlewares[manifest.id] = factory

    def register_sandbox(self, manifest: PluginManifest, factory: SandboxFactory) -> None:
        if manifest.kind != PluginKind.SANDBOX:
            raise PluginBindingError(
                "plugin.kind_mismatch",
                manifest.id,
                PluginKind.SANDBOX,
                registered_kinds=[manifest.kind.value],
            )
        self._register_manifest(manifest)
        self._sandboxes[manifest.id] = factory

    def register_manifest(self, manifest: PluginManifest) -> None:
        """Advertise a non-runtime plugin such as storage, bus, scheduler or UI."""
        self._register_manifest(manifest)

    def validate_binding(
        self,
        plugin_id: str,
        expected_kind: PluginKind,
        config: Dict[str, Any],
    ) -> PluginManifest:
        """Resolve a manifest and validate config without exposing config values."""

        key = (expected_kind, plugin_id)
        manifest = self._manifests.get(key)
        if manifest is None:
            registered_kinds = sorted(
                kind.value
                for kind, candidate_id in self._manifests
                if candidate_id == plugin_id
            )
            if registered_kinds:
                raise PluginBindingError(
                    "plugin.kind_mismatch",
                    plugin_id,
                    expected_kind,
                    registered_kinds=registered_kinds,
                )
            raise PluginBindingError(
                "plugin.not_found",
                plugin_id,
                expected_kind,
            )
        if not manifest.available:
            raise PluginBindingError(
                "plugin.unavailable",
                plugin_id,
                expected_kind,
            )
        factories = {
            PluginKind.PROVIDER: self._providers,
            PluginKind.TOOL: self._tools,
            PluginKind.SANDBOX: self._sandboxes,
            PluginKind.MEMORY: self._memories,
            PluginKind.MIDDLEWARE: self._middlewares,
        }[expected_kind]
        if plugin_id not in factories:
            raise PluginBindingError(
                "plugin.factory_missing",
                plugin_id,
                expected_kind,
            )

        validator = self._config_validators[key]
        violation = first_schema_violation(validator, config)
        if violation is not None:
            raise PluginBindingError(
                "plugin.config_invalid",
                plugin_id,
                expected_kind,
                path=violation.path,
                keyword=violation.keyword,
            )
        return manifest

    def validate_agent_spec(self, spec: AgentSpec) -> None:
        """Validate every binding, including disabled bindings, fail closed."""

        # Provider adapter/schema validation happens after the tenant ModelConfig
        # is resolved. Agent revisions intentionally store only model_config_id.
        for binding in spec.tools:
            self.validate_binding(
                binding.plugin_id,
                PluginKind.TOOL,
                binding.config,
            )
        self.validate_binding(
            spec.memory.plugin_id,
            PluginKind.MEMORY,
            spec.memory.config,
        )
        for binding in spec.middlewares:
            self.validate_binding(
                binding.plugin_id,
                PluginKind.MIDDLEWARE,
                binding.config,
            )

    def _factory(
        self,
        factories: Dict[str, Any],
        plugin_id: str,
        expected_kind: PluginKind,
    ) -> Any:
        try:
            return factories[plugin_id]
        except KeyError as exc:
            raise PluginBindingError(
                "plugin.factory_missing",
                plugin_id,
                expected_kind,
            ) from exc

    def create_provider(self, binding: ModelBinding) -> ModelProvider:
        self.validate_binding(
            binding.provider,
            PluginKind.PROVIDER,
            binding.config,
        )
        return self._factory(
            self._providers,
            binding.provider,
            PluginKind.PROVIDER,
        )(binding)

    def create_tool(self, binding: ToolBinding) -> ToolPlugin:
        self.validate_binding(
            binding.plugin_id,
            PluginKind.TOOL,
            binding.config,
        )
        return self._factory(
            self._tools,
            binding.plugin_id,
            PluginKind.TOOL,
        )(binding)

    def create_sandbox(self, binding: SandboxBinding) -> SandboxProvider:
        self.validate_binding(
            binding.plugin_id,
            PluginKind.SANDBOX,
            binding.config,
        )
        return self._factory(
            self._sandboxes,
            binding.plugin_id,
            PluginKind.SANDBOX,
        )(binding)

    def create_memory(self, binding: MemoryBinding) -> MemoryStore:
        self.validate_binding(
            binding.plugin_id,
            PluginKind.MEMORY,
            binding.config,
        )
        return self._factory(
            self._memories,
            binding.plugin_id,
            PluginKind.MEMORY,
        )(binding)

    def create_middlewares(self, bindings: List[MiddlewareBinding]) -> List[Middleware]:
        result: List[Middleware] = []
        for binding in bindings:
            self.validate_binding(
                binding.plugin_id,
                PluginKind.MIDDLEWARE,
                binding.config,
            )
            if not binding.enabled:
                continue
            factory = self._factory(
                self._middlewares,
                binding.plugin_id,
                PluginKind.MIDDLEWARE,
            )
            result.append(factory(binding))
        return result

    def manifests(self, kind: PluginKind = None) -> List[PluginManifest]:
        values = list(self._manifests.values())
        if kind is not None:
            values = [item for item in values if item.kind == kind]
        return sorted(values, key=lambda item: (item.kind.value, item.display_name.lower()))

    def manifest(self, plugin_id: str, kind: PluginKind) -> Optional[PluginManifest]:
        """Return registered manifest metadata without exposing an implementation."""

        return self._manifests.get((kind, plugin_id))

    def discover_entry_points(self) -> None:
        """Load third-party plugin bundles without making discovery fatal."""
        try:
            entry_points = metadata.entry_points()
            selected = (
                entry_points.select(group="uai_forge.plugins")
                if hasattr(entry_points, "select")
                else entry_points.get("uai_forge.plugins", [])
            )
        except Exception as exc:  # pragma: no cover - defensive around packaging runtimes
            self.discovery_errors.append(f"entry point discovery failed: {exc}")
            return
        for entry_point in selected:
            try:
                plugin = entry_point.load()
                instance: Any = plugin() if isinstance(plugin, type) else plugin
                instance.register(self)
            except Exception as exc:  # one bad extension must not stop the control plane
                self.discovery_errors.append(f"{entry_point.name}: {exc}")
