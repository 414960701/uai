"""FastAPI control plane."""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from . import __version__
from .container import Container
from .models import (
    AgentInstance,
    AgentPatch,
    AgentSpec,
    GraphValidationResult,
    InstancePatch,
    ModelConfig,
    ModelConfigPatch,
    ModelConfigWrite,
    PluginKind,
    PluginManifest,
    RuntimeConfigEntry,
    RuntimeConfigPatch,
    RunEvent,
    RunRecord,
    RunRequest,
    new_id,
)
from .registry import PluginBindingError
from .settings import Settings
from .storage import (
    ConfigurationConflictError,
    RevisionConflictError,
)


def create_app(settings: Settings = None) -> FastAPI:
    resolved = settings or Settings()
    container = Container.build(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await container.repository.initialize()
        app.state.container = container
        try:
            yield
        finally:
            await container.runs.shutdown()

    app = FastAPI(
        title="UAI Forge Control API",
        version=__version__,
        description="Versioned control plane for extensible single- and multi-agent runtimes.",
        lifespan=lifespan,
    )
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(PluginBindingError)
    async def plugin_binding_error(
        request: Request,
        exc: PluginBindingError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422,
            content={"detail": exc.as_detail()},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # FastAPI normally echoes the rejected input.  That is unsafe for a
        # one-time credential submission, so validation responses use the same
        # input-free shape as Agent patch validation.
        del request
        return JSONResponse(
            status_code=422,
            content={"detail": validation_error_detail(exc)},
        )

    def get_container(request: Request) -> Container:
        return request.app.state.container

    async def authorize(
        authorization: Optional[str] = Header(default=None),
        x_control_key: Optional[str] = Header(default=None),
    ) -> None:
        if not resolved.control_api_key:
            return
        bearer = (
            authorization[len("Bearer ") :]
            if authorization and authorization.startswith("Bearer ")
            else None
        )
        if bearer != resolved.control_api_key and x_control_key != resolved.control_api_key:
            raise HTTPException(status_code=401, detail="invalid control-plane credential")

    async def tenant_id(x_tenant_id: str = Header(default="default")) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", x_tenant_id):
            raise HTTPException(status_code=400, detail="invalid tenant id")
        return x_tenant_id

    protected = [Depends(authorize)]

    def validation_error_detail(exc: ValidationError) -> list:
        try:
            errors = exc.errors(include_input=False)
        except TypeError:  # FastAPI's RequestValidationError on Pydantic 2.10
            errors = exc.errors()
        return [
            {
                "type": item["type"],
                "loc": list(item["loc"]),
                "msg": item["msg"],
            }
            for item in errors
        ]

    async def validate_model_config_reference(
        current: Container,
        tenant: str,
        config_id: str,
        overrides: Optional[dict] = None,
    ) -> None:
        model_config = await current.repository.get_model_config(tenant, config_id)
        if model_config is None:
            raise HTTPException(status_code=422, detail="model configuration not found")
        if not model_config.enabled:
            raise HTTPException(status_code=422, detail="model configuration is disabled")
        config = {**model_config.config, **(overrides or {})}
        if model_config.base_url:
            config.setdefault("base_url", model_config.base_url)
        try:
            current.registry.validate_binding(
                model_config.provider,
                PluginKind.PROVIDER,
                config,
            )
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        manifest = current.registry.manifest(model_config.provider, PluginKind.PROVIDER)
        if manifest is not None and manifest.credential_required:
            secret = await current.repository.resolve_model_config_secret(tenant, config_id)
            if not secret:
                raise HTTPException(status_code=422, detail="model configuration secret is unavailable")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/system", dependencies=protected)
    async def system_info(
        current: Container = Depends(get_container),
    ) -> dict:
        return {
            "name": "UAI Forge",
            "version": __version__,
            "plugin_protocol": "1.x",
            "features": [
                "versioned_agents",
                "agent_instances",
                "mounted_subagents",
                "event_replay",
                "budget_guards",
                "plugin_entry_points",
                "database_backed_model_configs",
                "anthropic_messages",
                "versioned_runtime_config",
            ],
            "plugin_discovery_errors": current.registry.discovery_errors,
        }

    @app.get("/api/v1/plugins", response_model=List[PluginManifest], dependencies=protected)
    async def list_plugins(
        kind: Optional[PluginKind] = None,
        current: Container = Depends(get_container),
    ) -> List[PluginManifest]:
        return current.registry.manifests(kind)

    @app.get(
        "/api/v1/model-configs",
        response_model=List[ModelConfig],
        dependencies=protected,
    )
    async def list_model_configs(
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[ModelConfig]:
        return await current.repository.list_model_configs(tenant)

    @app.post(
        "/api/v1/model-configs",
        response_model=ModelConfig,
        status_code=status.HTTP_201_CREATED,
        dependencies=protected,
    )
    async def create_model_config(
        payload: ModelConfigWrite,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ModelConfig:
        config_id = payload.id or new_id("cfg")
        if await current.repository.get_model_config(tenant, config_id):
            raise HTTPException(status_code=409, detail="model configuration id already exists")
        manifest = current.registry.manifest(payload.provider, PluginKind.PROVIDER)
        if manifest is None:
            raise HTTPException(status_code=422, detail="model provider is unavailable")
        if manifest.credential_required and not payload.secret:
            raise HTTPException(status_code=422, detail="this provider requires a secret")
        try:
            config = dict(payload.config)
            if payload.base_url:
                config.setdefault("base_url", payload.base_url)
            current.registry.validate_binding(payload.provider, PluginKind.PROVIDER, config)
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        model_config = ModelConfig(
            id=config_id,
            tenant_id=tenant,
            name=payload.name,
            provider=payload.provider,
            protocol=manifest.api_protocol,
            model=payload.model,
            base_url=payload.base_url,
            config=payload.config,
            metadata=payload.metadata,
            enabled=payload.enabled,
        )
        return await current.repository.save_model_config(tenant, model_config, payload.secret)

    @app.get(
        "/api/v1/model-configs/{config_id}",
        response_model=ModelConfig,
        dependencies=protected,
    )
    async def get_model_config(
        config_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ModelConfig:
        model_config = await current.repository.get_model_config(tenant, config_id)
        if model_config is None:
            raise HTTPException(status_code=404, detail="model configuration not found")
        return model_config

    @app.patch(
        "/api/v1/model-configs/{config_id}",
        response_model=ModelConfig,
        dependencies=protected,
    )
    async def update_model_config(
        config_id: str,
        patch: ModelConfigPatch,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ModelConfig:
        existing = await current.repository.get_model_config(tenant, config_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="model configuration not found")
        data = existing.model_dump()
        data.update(patch.model_dump(exclude_unset=True, exclude={"secret"}))
        provider = str(data["provider"])
        manifest = current.registry.manifest(provider, PluginKind.PROVIDER)
        if manifest is None:
            raise HTTPException(status_code=422, detail="model provider is unavailable")
        if provider != existing.provider and patch.secret is None and manifest.credential_required:
            raise HTTPException(status_code=422, detail="changing provider requires a new secret")
        if manifest.credential_required and patch.secret is None:
            existing_secret = await current.repository.resolve_model_config_secret(tenant, config_id)
            if not existing_secret:
                raise HTTPException(status_code=422, detail="this provider requires a secret")
        data["protocol"] = manifest.api_protocol
        candidate = ModelConfig.model_validate(data)
        try:
            config = dict(candidate.config)
            if candidate.base_url:
                config.setdefault("base_url", candidate.base_url)
            current.registry.validate_binding(candidate.provider, PluginKind.PROVIDER, config)
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        return await current.repository.save_model_config(tenant, candidate, patch.secret)

    @app.delete(
        "/api/v1/model-configs/{config_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=protected,
    )
    async def delete_model_config(
        config_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> Response:
        if await current.repository.model_config_is_referenced(tenant, config_id):
            raise HTTPException(status_code=409, detail="model configuration is used by an agent")
        if not await current.repository.delete_model_config(tenant, config_id):
            raise HTTPException(status_code=404, detail="model configuration not found")
        return Response(status_code=204)

    @app.get(
        "/api/v1/runtime-config",
        response_model=List[RuntimeConfigEntry],
        dependencies=protected,
    )
    async def list_runtime_config(
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[RuntimeConfigEntry]:
        return await current.repository.list_runtime_configs(tenant)

    @app.patch(
        "/api/v1/runtime-config",
        response_model=RuntimeConfigEntry,
        dependencies=protected,
    )
    async def patch_runtime_config(
        patch: RuntimeConfigPatch,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> RuntimeConfigEntry:
        try:
            return await current.repository.save_runtime_config(
                tenant,
                patch.key,
                patch.value,
                expected_version=patch.expected_version,
            )
        except ConfigurationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/config/catalog", dependencies=protected)
    async def configuration_catalog(
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> dict:
        return {
            "model_configs": await current.repository.list_model_configs(tenant),
            "runtime": await current.repository.list_runtime_configs(tenant),
        }

    @app.get("/api/v1/model-catalog", dependencies=protected)
    async def model_catalog(current: Container = Depends(get_container)) -> dict:
        providers = []
        for manifest in current.registry.manifests(PluginKind.PROVIDER):
            providers.append(
                {
                    "id": manifest.id,
                    "display_name": manifest.display_name,
                    "description": manifest.description,
                    "api_protocol": manifest.api_protocol,
                    "credential_required": manifest.credential_required,
                    "homepage": manifest.homepage,
                    "models": manifest.model_catalog,
                }
            )
        return {"providers": providers}

    @app.get("/api/v1/agents", response_model=List[AgentSpec], dependencies=protected)
    async def list_agents(
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[AgentSpec]:
        return await current.repository.list_agents(tenant)

    @app.post(
        "/api/v1/agents",
        response_model=AgentSpec,
        status_code=status.HTTP_201_CREATED,
        dependencies=protected,
    )
    async def create_agent(
        spec: AgentSpec,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentSpec:
        current.registry.validate_agent_spec(spec)
        await validate_model_config_reference(
            current, tenant, spec.model.model_config_id, spec.model.config
        )
        existing = await current.repository.get_agent(tenant, spec.id)
        if existing:
            raise HTTPException(status_code=409, detail="agent id already exists")
        return await current.repository.save_agent(tenant, spec)

    @app.get("/api/v1/agents/{agent_id}", response_model=AgentSpec, dependencies=protected)
    async def get_agent(
        agent_id: str,
        revision: Optional[int] = None,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentSpec:
        spec = await current.repository.get_agent(tenant, agent_id, revision)
        if spec is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return spec

    @app.patch("/api/v1/agents/{agent_id}", response_model=AgentSpec, dependencies=protected)
    async def update_agent(
        agent_id: str,
        patch: AgentPatch,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentSpec:
        spec = await current.repository.get_agent(tenant, agent_id)
        if spec is None:
            raise HTTPException(status_code=404, detail="agent not found")
        changes = patch.model_dump(exclude={"expected_revision"}, exclude_none=True)
        candidate_data = spec.model_dump()
        candidate_data.update(changes)
        try:
            candidate = AgentSpec.model_validate(candidate_data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=validation_error_detail(exc),
            ) from exc
        current.registry.validate_agent_spec(candidate)
        await validate_model_config_reference(
            current, tenant, candidate.model.model_config_id, candidate.model.config
        )
        try:
            return await current.repository.save_agent(
                tenant, candidate, expected_revision=patch.expected_revision
            )
        except RevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete(
        "/api/v1/agents/{agent_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=protected,
    )
    async def delete_agent(
        agent_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> Response:
        agents = await current.repository.list_agents(tenant)
        references = [
            item.id
            for item in agents
            if any(mount.agent_id == agent_id for mount in item.children)
        ]
        instances = [
            item.id
            for item in await current.repository.list_instances(tenant)
            if item.agent_id == agent_id
        ]
        if references or instances:
            raise HTTPException(
                status_code=409,
                detail={"mounted_by": references, "instances": instances},
            )
        if not await current.repository.delete_agent(tenant, agent_id):
            raise HTTPException(status_code=404, detail="agent not found")
        return Response(status_code=204)

    @app.get(
        "/api/v1/agents/{agent_id}/revisions",
        response_model=List[AgentSpec],
        dependencies=protected,
    )
    async def list_revisions(
        agent_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[AgentSpec]:
        return await current.repository.list_agent_revisions(tenant, agent_id)

    @app.post(
        "/api/v1/agents/{agent_id}/validate",
        response_model=GraphValidationResult,
        dependencies=protected,
    )
    async def validate_agent(
        agent_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> GraphValidationResult:
        return await current.validator.validate(tenant, agent_id)

    @app.get(
        "/api/v1/agents/{agent_id}/topology",
        response_model=GraphValidationResult,
        dependencies=protected,
    )
    async def topology(
        agent_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> GraphValidationResult:
        return await current.validator.validate(tenant, agent_id)

    @app.get(
        "/api/v1/instances",
        response_model=List[AgentInstance],
        dependencies=protected,
    )
    async def list_instances(
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[AgentInstance]:
        return await current.repository.list_instances(tenant)

    @app.post(
        "/api/v1/instances",
        response_model=AgentInstance,
        status_code=status.HTTP_201_CREATED,
        dependencies=protected,
    )
    async def create_instance(
        instance: AgentInstance,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentInstance:
        if await current.repository.get_instance(tenant, instance.id):
            raise HTTPException(status_code=409, detail="instance id already exists")
        agent = await current.repository.get_agent(
            tenant, instance.agent_id, instance.agent_revision
        )
        if agent is None:
            raise HTTPException(status_code=422, detail="referenced agent revision not found")
        return await current.repository.save_instance(tenant, instance)

    @app.get(
        "/api/v1/instances/{instance_id}",
        response_model=AgentInstance,
        dependencies=protected,
    )
    async def get_instance(
        instance_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentInstance:
        instance = await current.repository.get_instance(tenant, instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="instance not found")
        return instance

    @app.patch(
        "/api/v1/instances/{instance_id}",
        response_model=AgentInstance,
        dependencies=protected,
    )
    async def update_instance(
        instance_id: str,
        patch: InstancePatch,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentInstance:
        instance = await current.repository.get_instance(tenant, instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="instance not found")
        candidate_data = instance.model_dump()
        candidate_data.update(patch.model_dump(exclude_none=True))
        try:
            candidate = AgentInstance.model_validate(candidate_data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=validation_error_detail(exc),
            ) from exc
        agent = await current.repository.get_agent(
            tenant, candidate.agent_id, candidate.agent_revision
        )
        if agent is None:
            raise HTTPException(status_code=422, detail="referenced agent revision not found")
        return await current.repository.save_instance(tenant, candidate)

    @app.delete(
        "/api/v1/instances/{instance_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=protected,
    )
    async def delete_instance(
        instance_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> Response:
        if not await current.repository.delete_instance(tenant, instance_id):
            raise HTTPException(status_code=404, detail="instance not found")
        return Response(status_code=204)

    @app.get("/api/v1/runs", response_model=List[RunRecord], dependencies=protected)
    async def list_runs(
        limit: int = 100,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[RunRecord]:
        return await current.repository.list_runs(tenant, limit)

    @app.post(
        "/api/v1/runs",
        response_model=RunRecord,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=protected,
    )
    async def start_run(
        run_request: RunRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> RunRecord:
        try:
            return await current.runs.start(tenant, run_request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}", response_model=RunRecord, dependencies=protected)
    async def get_run(
        run_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> RunRecord:
        run = await current.repository.get_run(tenant, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.post("/api/v1/runs/{run_id}/cancel", dependencies=protected)
    async def cancel_run(
        run_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> dict:
        if not await current.runs.cancel(tenant, run_id):
            raise HTTPException(status_code=409, detail="run is not active")
        return {"accepted": True, "run_id": run_id}

    @app.get(
        "/api/v1/runs/{run_id}/events/history",
        response_model=List[RunEvent],
        dependencies=protected,
    )
    async def run_event_history(
        run_id: str,
        after: int = 0,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[RunEvent]:
        if await current.repository.get_run(tenant, run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")
        return await current.repository.list_events(tenant, run_id, max(0, after))

    @app.get("/api/v1/runs/{run_id}/events", dependencies=protected)
    async def run_events(
        run_id: str,
        request: Request,
        after: int = 0,
        last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> StreamingResponse:
        if await current.repository.get_run(tenant, run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")
        if last_event_id and last_event_id.isdigit():
            after = max(after, int(last_event_id))

        async def stream() -> AsyncIterator[str]:
            async for event in current.events.subscribe(tenant, run_id, after):
                if await request.is_disconnected():
                    return
                if event is None:
                    yield ": keepalive\n\n"
                    continue
                payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                yield f"id: {event.sequence}\nevent: {event.type.value}\ndata: {payload}\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
