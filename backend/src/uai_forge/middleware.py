"""Reference middleware implementations."""

from __future__ import annotations

from typing import Any, Dict

from .models import MiddlewareBinding, PluginKind, PluginManifest
from .ports import Middleware, ModelOutput, ModelRequest


AUDIT_MIDDLEWARE_MANIFEST = PluginManifest(
    id="middleware.audit_tags",
    kind=PluginKind.MIDDLEWARE,
    display_name="Audit tag middleware",
    version="1.0.0",
    description="Adds non-sensitive execution tags to provider metadata.",
    capabilities=["before_model", "stateless", "concurrency_safe"],
    config_schema={
        "type": "object",
        "properties": {"tags": {"type": "object", "additionalProperties": {"type": "string"}}},
        "additionalProperties": False,
    },
)


class AuditTagMiddleware(Middleware):
    manifest = AUDIT_MIDDLEWARE_MANIFEST

    def __init__(self, binding: MiddlewareBinding) -> None:
        self.tags = dict(binding.config.get("tags", {}))

    async def before_model(self, context: Dict[str, Any], request: ModelRequest) -> ModelRequest:
        metadata = {**request.metadata, "audit_tags": self.tags}
        return request.model_copy(update={"metadata": metadata})

    async def after_model(self, context: Dict[str, Any], output: ModelOutput) -> ModelOutput:
        return output


def create_audit_tags(binding: MiddlewareBinding) -> Middleware:
    return AuditTagMiddleware(binding)
