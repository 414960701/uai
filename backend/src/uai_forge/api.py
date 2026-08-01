"""FastAPI control plane."""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from . import __version__
from .container import Container
from .models import (
    AgentPublishRequest,
    AgentPatch,
    AgentRevisionInfo,
    AgentRollbackRequest,
    AgentSpec,
    GraphValidationResult,
    ModelConfig,
    ModelConfigPatch,
    ModelConfigReferences,
    ModelConfigVerification,
    ModelBinding,
    ModelConnectionCheckRequest,
    ModelConnectionCheckResult,
    ModelConfigWrite,
    AgentReadiness,
    CapabilityStatus,
    ChoiceResolutionRequest,
    ExecutionPlan,
    PlanApprovalRequest,
    PlanEditRequest,
    ProblemDetails,
    ProblemFieldError,
    ProblemResource,
    ReadinessIssue,
    Remediation,
    SetupResourceSummary,
    SetupStatus,
    PluginKind,
    PluginManifest,
    RuntimeConfigEntry,
    RuntimeConfigPatch,
    RunEvent,
    RunRecord,
    RunRequest,
    default_tool_bindings,
    new_id,
    utc_now,
)
from .registry import PluginBindingError
from .settings import Settings
from .endpoints import EndpointPolicyError, endpoint_summary, validate_endpoint_url
from .storage import (
    ConfigurationConflictError,
    RecordNotFoundError,
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

    def problem_response(
        *,
        request: Optional[Request],
        status_code: int,
        code: str,
        message: str,
        field_errors: Optional[List[ProblemFieldError]] = None,
        resource: Optional[ProblemResource] = None,
        retryable: bool = False,
        remediation: Optional[Remediation] = None,
        legacy_detail: Any = None,
    ) -> JSONResponse:
        del request
        correlation_id = new_id("cor")
        problem = ProblemDetails(
            code=code,
            message=message,
            field_errors=field_errors or [],
            resource=resource,
            retryable=retryable,
            remediation=remediation,
            correlation_id=correlation_id,
        )
        body = problem.model_dump(mode="json")
        # Keep the old detail field for adapters and 0.1 consumers while the
        # top-level Problem Details shape becomes the canonical contract.
        if legacy_detail is not None:
            body["detail"] = legacy_detail
        return JSONResponse(
            status_code=status_code,
            content=body,
            headers={"X-Correlation-ID": correlation_id},
        )

    def problem_for_http_exception(exc: HTTPException) -> Dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else ""
        lower = detail.lower()
        safe_detail_codes = {
            "endpoint.scheme_not_allowed": (
                "端点协议不被允许",
                Remediation(action="review_endpoint", target="model-config"),
            ),
            "endpoint.userinfo_not_allowed": (
                "端点不得包含用户名或密码",
                Remediation(action="review_endpoint", target="model-config"),
            ),
            "endpoint.host_required": (
                "端点必须包含主机名",
                Remediation(action="review_endpoint", target="model-config"),
            ),
            "endpoint.query_or_fragment_not_allowed": (
                "端点不得包含查询参数或片段",
                Remediation(action="review_endpoint", target="model-config"),
            ),
            "endpoint.private_address_not_allowed": (
                "端点目标地址未通过部署安全策略",
                Remediation(action="review_endpoint_policy", target="model-config"),
            ),
            "endpoint.https_required": (
                "公网模型端点必须使用 HTTPS",
                Remediation(action="review_endpoint", target="model-config"),
            ),
            "endpoint.port_invalid": (
                "端口号无效",
                Remediation(action="review_endpoint", target="model-config"),
            ),
        }
        if detail in safe_detail_codes:
            message, remediation = safe_detail_codes[detail]
            return {
                "code": detail,
                "message": message,
                "remediation": remediation,
            }
        if exc.status_code == 401:
            return {
                "code": "auth.invalid",
                "message": "控制面凭证无效或未提供",
                "remediation": Remediation(action="configure_control_credential", target="settings"),
            }
        if exc.status_code == 404:
            return {
                "code": "resource.not_found",
                "message": "请求的资源不存在或不属于当前数据分区",
                "remediation": Remediation(action="reload", target="current_resource"),
            }
        if exc.status_code == 409:
            if "version" in lower or "revision" in lower:
                return {
                    "code": "resource.version_conflict",
                    "message": "资源已被其他操作更新，请重新加载后比较",
                    "retryable": True,
                    "remediation": Remediation(action="reload_and_compare", target="current_resource"),
                }
            return {
                "code": "resource.conflict",
                "message": "当前操作与资源状态冲突",
                "remediation": Remediation(action="review_resource", target="current_resource"),
            }
        if exc.status_code == 428:
            return {
                "code": "request.version_required",
                "message": "更新操作需要携带资源版本",
                "remediation": Remediation(action="reload_and_retry", target="current_resource"),
            }
        if exc.status_code == 422:
            if "model configuration" in lower or "model config" in lower:
                return {
                    "code": "model_config.unavailable",
                    "message": "模型连接当前不可运行，请检查状态和验证结果",
                    "remediation": Remediation(action="open_model_config", target="model-configs"),
                }
            return {
                "code": "request.rejected",
                "message": "请求未通过配置、权限或能力校验",
                "remediation": Remediation(action="review_fields", target="request"),
            }
        if exc.status_code == 400:
            return {
                "code": "request.invalid",
                "message": "请求格式或数据分区无效",
                "remediation": Remediation(action="review_fields", target="request"),
            }
        return {
            "code": "server.request_failed",
            "message": "控制面暂时无法完成请求",
            "retryable": exc.status_code >= 500,
            "remediation": Remediation(action="retry", target="request") if exc.status_code >= 500 else None,
        }

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        details = problem_for_http_exception(exc)
        return problem_response(request=request, status_code=exc.status_code, **details)

    @app.exception_handler(PluginBindingError)
    async def plugin_binding_error(
        request: Request,
        exc: PluginBindingError,
    ) -> JSONResponse:
        details = exc.as_detail()
        return problem_response(
            request=request,
            status_code=422,
            code=str(details.get("code", "plugin.binding_invalid")),
            message="扩展绑定未通过协议或配置校验",
            remediation=Remediation(action="review_plugin_config", target=exc.plugin_id),
            legacy_detail=details,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # FastAPI normally echoes the rejected input.  That is unsafe for a
        # one-time credential submission, so validation responses use the same
        # input-free shape as Agent patch validation.
        errors = validation_error_detail(exc)
        field_errors = [
            ProblemFieldError(
                field=".".join(str(part) for part in item["loc"]),
                code=str(item["type"]),
                message="输入未通过校验",
            )
            for item in errors
        ]
        return problem_response(
            request=request,
            status_code=422,
            code="request.invalid",
            message="请求包含无效字段",
            field_errors=field_errors,
            remediation=Remediation(action="review_fields", target="request"),
            legacy_detail=errors,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Keep provider, storage, and framework exception text out of the
        # public contract.  The process-level logger/telemetry boundary may
        # record a separately redacted diagnostic, but HTTP clients receive
        # only the stable, actionable Problem Details shape.
        del exc
        return problem_response(
            request=request,
            status_code=500,
            code="server.internal_error",
            message="控制面暂时无法完成请求",
            retryable=True,
            remediation=Remediation(action="retry", target="request"),
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
        if not model_config.enabled or model_config.lifecycle != "enabled":
            raise HTTPException(status_code=422, detail="model configuration is disabled")
        config = {**model_config.config, **(overrides or {})}
        if model_config.base_url:
            config.setdefault("base_url", model_config.base_url)
        try:
            validate_endpoint_url(
                config.get("base_url"),
                allow_local=resolved.allow_local_provider_endpoints,
            )
        except EndpointPolicyError as exc:
            raise HTTPException(status_code=422, detail=exc.code) from exc
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

    async def agent_readiness_for(
        current: Container,
        tenant: str,
        agent_id: str,
        revision: Optional[int] = None,
    ) -> AgentReadiness:
        spec = await current.repository.get_agent(tenant, agent_id, revision)
        resolved_revision = revision or (spec.revision if spec else 0)
        issues: List[ReadinessIssue] = []

        def issue(
            code: str,
            message: str,
            *,
            resource_type: str = "agent",
            resource_id: Optional[str] = None,
            path: Optional[str] = None,
            action: str = "review_resource",
            target: Optional[str] = None,
        ) -> None:
            issues.append(
                ReadinessIssue(
                    code=code,
                    resource_type=resource_type,
                    resource_id=resource_id or agent_id,
                    path=path,
                    message=message,
                    remediation=Remediation(action=action, target=target or agent_id),
                )
            )

        if spec is None:
            issue(
                "agent.missing",
                "Agent 或固定修订不存在",
                action="create_agent",
                target="agents",
            )
            return AgentReadiness(agent_id=agent_id, revision=resolved_revision, runnable=False, issues=issues)
        if not spec.enabled:
            issue("agent.disabled", "Agent 已停用", action="enable_agent")

        model_config = await current.repository.get_model_config(tenant, spec.model.model_config_id)
        if model_config is None:
            issue(
                "model_config.missing",
                "Agent 引用的模型连接不存在",
                resource_type="model_config",
                resource_id=spec.model.model_config_id,
                path="model.model_config_id",
                action="create_model_config",
                target="model-configs",
            )
        else:
            if model_config.lifecycle in {"disabled", "error"} or not model_config.enabled:
                issue(
                    "model_config.disabled",
                    "模型连接已停用或处于错误状态",
                    resource_type="model_config",
                    resource_id=model_config.id,
                    action="open_model_config",
                    target=model_config.id,
                )
            elif model_config.lifecycle != "enabled":
                issue(
                    "model_config.unverified",
                    "模型连接尚未验证并启用",
                    resource_type="model_config",
                    resource_id=model_config.id,
                    action="verify_model_config",
                    target=model_config.id,
                )
            config = {**model_config.config, **spec.model.config}
            if model_config.base_url:
                config.setdefault("base_url", model_config.base_url)
            try:
                validate_endpoint_url(
                    config.get("base_url"),
                    allow_local=resolved.allow_local_provider_endpoints,
                )
                current.registry.validate_binding(model_config.provider, PluginKind.PROVIDER, config)
            except EndpointPolicyError:
                issue(
                    "provider.endpoint_invalid",
                    "模型连接端点未通过安全策略",
                    resource_type="model_config",
                    resource_id=model_config.id,
                    action="open_model_config",
                    target=model_config.id,
                )
            except PluginBindingError as exc:
                issue(
                    exc.code,
                    "模型连接的 Provider 配置无效",
                    resource_type="model_config",
                    resource_id=model_config.id,
                    action="open_model_config",
                    target=model_config.id,
                )
            manifest = current.registry.manifest(model_config.provider, PluginKind.PROVIDER)
            if manifest is None or not manifest.available:
                issue(
                    "provider.unavailable",
                    "模型 Provider 当前不可用",
                    resource_type="model_config",
                    resource_id=model_config.id,
                    action="open_plugins",
                    target="plugins",
                )
            elif manifest.credential_required and model_config.lifecycle == "enabled":
                try:
                    secret = await current.repository.resolve_model_config_secret(tenant, model_config.id)
                except RuntimeError:
                    secret = None
                if not secret:
                    issue(
                        "model_config.secret_unavailable",
                        "模型连接凭证不可用，请重新替换密钥",
                        resource_type="model_config",
                        resource_id=model_config.id,
                        action="open_model_config",
                        target=model_config.id,
                    )

        try:
            current.registry.validate_agent_spec(spec)
        except PluginBindingError as exc:
            issue(
                exc.code,
                "Agent 的扩展绑定未通过校验",
                path=exc.path,
                action="open_agent",
                target=agent_id,
            )
        graph = await current.validator.validate(tenant, agent_id, revision)
        for graph_issue in graph.issues:
            mapped = {
                "mount_cycle": "agent.topology_invalid",
                "missing_agent": "agent.topology_invalid",
                "missing_revision": "agent.topology_invalid",
                "disabled_agent": "agent.disabled",
            }.get(graph_issue.code, "agent.topology_invalid")
            issue(
                mapped,
                "Agent 协作拓扑未通过运行前校验",
                path="/".join(graph_issue.path),
                action="open_topology",
                target=agent_id,
            )
        return AgentReadiness(
            agent_id=agent_id,
            revision=resolved_revision,
            runnable=not issues,
            issues=issues,
        )

    def capability_statuses(current: Container) -> List[CapabilityStatus]:
        return [
            CapabilityStatus(
                id="bounded_nested_calls",
                state="implemented",
                summary="单进程内 bounded child 调用受根预算、深度、权限和取消传播保护",
                limits=["不等同 durable peer", "不提供崩溃后自动续跑"],
                evidence_refs=["backend/tests/test_multi_agent_policy.py"],
            ),
            CapabilityStatus(
                id="sqlite_event_replay",
                state="implemented",
                summary="SQLite 持久化 Run Event，支持按 sequence 历史回放和单进程 SSE",
                limits=["单写节点", "不等同分布式消息总线"],
                evidence_refs=["backend/tests/test_api.py::test_run_lifecycle_from_agent_revision"],
            ),
            CapabilityStatus(
                id="provider_connection_checks",
                state="implemented",
                summary="内置 Provider 通过自有协议执行无 prompt 的低成本连接检查",
                limits=["第三方 Provider 需自行实现并通过 TCK"],
                evidence_refs=["backend/src/uai_forge/providers.py"],
            ),
            CapabilityStatus(
                id="single_process_runtime",
                state="implemented",
                summary="当前控制面以单 Python 进程、SQLite 和进程内事件总线运行",
                limits=["不提供 worker lease、checkpoint 或崩溃后自动续跑"],
                evidence_refs=["docs/architecture/deployment.md"],
            ),
            CapabilityStatus(
                id="single_node_container",
                state="implemented",
                summary="单节点 Compose 形态有双镜像、健康、doctor、schema 和空库 smoke 证据",
                limits=["单 worker、单写 SQLite；不等同可恢复云集群"],
                evidence_refs=["scripts/container-smoke.sh"],
            ),
            CapabilityStatus(
                id="durable_cloud",
                state="planned",
                summary="PostgreSQL、durable bus、checkpoint、lease/fencing 和 OTel 属于后续部署形态",
                limits=["尚无分布式恢复、多副本故障或可信云身份证据"],
                evidence_refs=["docs/architecture/deployment.md"],
            ),
            CapabilityStatus(
                id="control_api_key",
                state="partial",
                summary="可选单一控制密钥；未认证上下文不代表 OIDC/RBAC 身份",
                limits=["无用户级角色", "tenant header 仍是 0.1 客户端分区边界"],
                evidence_refs=["docs/architecture/deployment.md"],
            ),
            CapabilityStatus(
                id="checkpoint_outbox_recovery",
                state="planned",
                summary="checkpoint、outbox、lease/fencing 和崩溃恢复属于后续版本",
                limits=["运行中进程终止不会自动续跑"],
                evidence_refs=["docs/architecture/adr/ADR-0005-at-least-once-recovery.md"],
            ),
            CapabilityStatus(
                id="plugin_isolation",
                state="partial",
                summary="显式 opt-in 的 Docker 子容器沙箱已接入，未知插件仍视为可信 in-process 代码",
                limits=["默认 Agent 不挂载", "rootless/dedicated executor 与生产级隔离仍待验收"],
                evidence_refs=[
                    "backend/src/uai_forge/sandbox.py",
                    "docs/architecture/adr/ADR-0010-extensible-sandbox-runtimes.md",
                ],
            ),
        ]

    @app.get("/api/v1/setup-status", response_model=SetupStatus, dependencies=protected)
    async def setup_status(
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> SetupStatus:
        configs = await current.repository.list_model_configs(tenant)
        agents = await current.repository.list_agents(tenant)
        runs = await current.repository.list_runs(tenant, limit=500)
        readiness = [await agent_readiness_for(current, tenant, item.id) for item in agents]
        config_issues: List[ReadinessIssue] = []
        for item in configs:
            if item.lifecycle != "enabled" or not item.enabled:
                config_issues.append(
                    ReadinessIssue(
                        code="model_config.unverified" if item.lifecycle in {"draft", "verified"} else "model_config.disabled",
                        resource_type="model_config",
                        resource_id=item.id,
                        message="模型连接尚未处于可运行状态",
                        remediation=Remediation(action="verify_model_config", target=item.id),
                    )
                )
        active_statuses = {"queued", "running"}
        terminal_times = [run.finished_at for run in runs if run.finished_at is not None]
        runnable_agents = sum(1 for item in readiness if item.runnable)
        runnable_configs = sum(1 for item in configs if item.enabled and item.lifecycle == "enabled")
        if not configs:
            next_action = "create_model_config"
        elif not runnable_configs:
            next_action = "verify_model_config"
        elif not agents:
            next_action = "create_agent"
        elif not runnable_agents:
            next_action = "create_agent"
        elif not any(run.status.value in active_statuses for run in runs):
            next_action = "run_agent"
        else:
            next_action = "none"
        return SetupStatus(
            connection="connected",
            model_connections=SetupResourceSummary(
                total=len(configs),
                runnable=runnable_configs,
                verified_enabled=sum(1 for item in configs if item.verification.status == "passed" and item.enabled),
                blocking_issues=config_issues,
            ),
            agents=SetupResourceSummary(
                total=len(agents),
                runnable=runnable_agents,
                blocking_issues=[issue for item in readiness for issue in item.issues][:50],
            ),
            runs=SetupResourceSummary(
                total=len(runs),
                active=sum(1 for run in runs if run.status.value in active_statuses),
                last_terminal_at=max(terminal_times) if terminal_times else None,
            ),
            next_action=next_action,
        )

    @app.get("/api/v1/capabilities", response_model=List[CapabilityStatus], dependencies=protected)
    async def capabilities(current: Container = Depends(get_container)) -> List[CapabilityStatus]:
        return capability_statuses(current)

    @app.get("/api/v1/agents/{agent_id}/readiness", response_model=AgentReadiness, dependencies=protected)
    async def agent_readiness(
        agent_id: str,
        revision: Optional[int] = None,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentReadiness:
        return await agent_readiness_for(current, tenant, agent_id, revision)

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
                "mounted_subagents",
                "event_replay",
                "budget_guards",
                "plugin_entry_points",
                "database_backed_model_configs",
                "anthropic_messages",
                "versioned_runtime_config",
            ],
            "capabilities": [item.model_dump(mode="json") for item in capability_statuses(current)],
            "storage": await current.repository.compatibility_status(),
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
        secret_action = payload.secret_action or ("replace" if payload.secret is not None else "clear")
        if secret_action == "clear" and payload.secret is not None:
            raise HTTPException(status_code=422, detail="secret_action clear cannot include a secret")
        if manifest.credential_required and not payload.secret:
            raise HTTPException(status_code=422, detail="this provider requires a secret")
        try:
            normalized_base_url = validate_endpoint_url(
                payload.base_url,
                allow_local=resolved.allow_local_provider_endpoints,
            )
        except EndpointPolicyError as exc:
            raise HTTPException(status_code=422, detail=exc.code) from exc
        try:
            config = dict(payload.config)
            if normalized_base_url:
                config.setdefault("base_url", normalized_base_url)
            current.registry.validate_binding(payload.provider, PluginKind.PROVIDER, config)
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        lifecycle = payload.lifecycle
        if lifecycle is None:
            lifecycle = "draft" if manifest.credential_required else ("enabled" if payload.enabled else "disabled")
        if manifest.credential_required and lifecycle == "enabled":
            raise HTTPException(
                status_code=409,
                detail="model configuration must pass a connection check before enabling",
            )
        model_config = ModelConfig(
            id=config_id,
            tenant_id=tenant,
            name=payload.name,
            provider=payload.provider,
            protocol=manifest.api_protocol,
            model=payload.model,
            base_url=normalized_base_url,
            config=payload.config,
            metadata=payload.metadata,
            enabled=payload.enabled,
            lifecycle=lifecycle,
        )
        try:
            return await current.repository.save_model_config(
                tenant,
                model_config,
                payload.secret,
                secret_action=secret_action,
            )
        except ConfigurationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
        if patch.expected_version is None:
            raise HTTPException(status_code=428, detail="model configuration version is required")
        data = existing.model_dump()
        changed_fields = set(patch.model_fields_set).intersection(
            {"name", "provider", "model", "base_url", "config", "metadata"}
        )
        patch_data = patch.model_dump(
            exclude_unset=True,
            exclude={"secret", "expected_version", "secret_action"},
        )
        data.update(patch_data)
        provider = str(data["provider"])
        manifest = current.registry.manifest(provider, PluginKind.PROVIDER)
        if manifest is None:
            raise HTTPException(status_code=422, detail="model provider is unavailable")
        if provider != existing.provider and patch.secret_action != "replace" and manifest.credential_required:
            raise HTTPException(status_code=422, detail="changing provider requires a new secret")
        if patch.secret_action == "clear" and manifest.credential_required:
            raise HTTPException(status_code=422, detail="this provider requires a secret")
        if manifest.credential_required and patch.secret_action == "keep":
            # A verified connection is intentionally not runnable until it is
            # explicitly enabled, so the normal resolver excludes it.  An
            # update with ``secret_action=keep`` still needs to validate the
            # retained credential before it can transition verified -> enabled
            # (or edit another field).  This is an internal, scoped lookup;
            # the secret remains outside the response and event contracts.
            existing_secret = await current.repository.resolve_model_config_secret(
                tenant,
                config_id,
                include_disabled=True,
            )
            if not existing_secret:
                raise HTTPException(status_code=422, detail="this provider requires a secret")
        data["protocol"] = manifest.api_protocol
        try:
            normalized_base_url = validate_endpoint_url(
                data.get("base_url"),
                allow_local=resolved.allow_local_provider_endpoints,
            )
        except EndpointPolicyError as exc:
            raise HTTPException(status_code=422, detail=exc.code) from exc
        data["base_url"] = normalized_base_url
        if (
            (changed_fields or patch.secret_action in {"replace", "clear"})
            and "lifecycle" not in patch.model_fields_set
        ):
            data["lifecycle"] = "draft"
            data["enabled"] = False
            data["verification"] = ModelConfigVerification().model_dump()
        elif patch.enabled is not None and "lifecycle" not in patch.model_fields_set:
            data["lifecycle"] = "enabled" if patch.enabled else "disabled"
        candidate = ModelConfig.model_validate(data)
        if (
            candidate.lifecycle == "enabled"
            and manifest.credential_required
            and candidate.verification.status != "passed"
        ):
            raise HTTPException(status_code=409, detail="model configuration must pass a connection check before enabling")
        try:
            config = dict(candidate.config)
            if candidate.base_url:
                config.setdefault("base_url", candidate.base_url)
            current.registry.validate_binding(candidate.provider, PluginKind.PROVIDER, config)
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        try:
            return await current.repository.save_model_config(
                tenant,
                candidate,
                patch.secret,
                expected_version=patch.expected_version,
                secret_action=patch.secret_action,
            )
        except ConfigurationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/model-configs/{config_id}/checks",
        response_model=ModelConnectionCheckResult,
        dependencies=protected,
    )
    async def check_model_config(
        config_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ModelConnectionCheckResult:
        existing = await current.repository.get_model_config(tenant, config_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="model configuration not found")
        manifest = current.registry.manifest(existing.provider, PluginKind.PROVIDER)
        if manifest is None or not manifest.available:
            raise HTTPException(status_code=422, detail="model provider is unavailable")
        config = dict(existing.config)
        if existing.base_url:
            config.setdefault("base_url", existing.base_url)
        try:
            normalized_base_url = validate_endpoint_url(
                config.get("base_url"),
                allow_local=resolved.allow_local_provider_endpoints,
            )
            current.registry.validate_binding(existing.provider, PluginKind.PROVIDER, config)
        except EndpointPolicyError as exc:
            raise HTTPException(status_code=422, detail=exc.code) from exc
        except PluginBindingError as exc:
            raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
        if manifest.connection_check == "none":
            return ModelConnectionCheckResult(
                status="partial",
                code="provider.connection_check_unsupported",
                checked_at=utc_now(),
                endpoint_summary=endpoint_summary(normalized_base_url),
                provider=existing.provider,
                model=existing.model,
            )
        secret = await current.repository.resolve_model_config_secret(
            tenant,
            config_id,
            include_disabled=True,
        )
        check_request = ModelConnectionCheckRequest(
            provider=existing.provider,
            protocol=existing.protocol,
            model=existing.model,
            base_url=normalized_base_url,
            config=config,
            credential=secret,
        )
        binding = ModelBinding(model_config_id=existing.id, config=config)
        binding._runtime_provider = existing.provider
        binding._runtime_protocol = existing.protocol
        binding._runtime_model = existing.model
        binding._runtime_credential = secret
        provider = current.registry.create_provider(binding)
        try:
            result = await provider.check(check_request)
        except Exception:
            # A provider adapter cannot make arbitrary exception text part of
            # the public contract.  The check remains safely failed.
            result = ModelConnectionCheckResult(
                status="failed",
                code="provider.connection_check_failed",
                provider=existing.provider,
                model=existing.model,
                endpoint_summary=endpoint_summary(normalized_base_url),
            )
        verification = ModelConfigVerification(
            status="passed" if result.status == "passed" else "failed" if result.status == "failed" else "never",
            checked_at=result.checked_at,
            code=result.code,
            latency_ms=result.latency_ms,
            endpoint_summary=result.endpoint_summary,
        )
        lifecycle = "verified" if result.status == "passed" else "error" if result.status == "failed" else existing.lifecycle
        candidate = existing.model_copy(
            update={
                "lifecycle": lifecycle,
                "enabled": lifecycle == "enabled",
                "verification": verification,
            }
        )
        try:
            await current.repository.save_model_config(
                tenant,
                candidate,
                expected_version=existing.version,
                secret_action="keep",
            )
        except ConfigurationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result

    @app.get(
        "/api/v1/model-configs/{config_id}/references",
        response_model=ModelConfigReferences,
        dependencies=protected,
    )
    async def model_config_references(
        config_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ModelConfigReferences:
        if await current.repository.get_model_config(tenant, config_id) is None:
            raise HTTPException(status_code=404, detail="model configuration not found")
        return await current.repository.list_model_config_references(
            tenant,
            config_id,
            limit=limit,
            cursor=cursor,
        )

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
        # Omitted tools means "use the safe first-party baseline" for a new
        # Agent. An explicit [] remains an intentional no-tool configuration,
        # so existing and least-privilege callers can opt out.
        if "tools" not in spec.model_fields_set:
            spec = spec.model_copy(update={"tools": default_tool_bindings()})
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

    async def save_agent_draft(
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
                tenant,
                candidate,
                expected_revision=patch.expected_revision,
                status="draft",
            )
        except RevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch("/api/v1/agents/{agent_id}", response_model=AgentSpec, dependencies=protected)
    async def update_agent(
        agent_id: str,
        patch: AgentPatch,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentSpec:
        return await save_agent_draft(agent_id, patch, tenant, current)

    @app.post(
        "/api/v1/agents/{agent_id}/draft",
        response_model=AgentSpec,
        dependencies=protected,
    )
    async def create_agent_draft(
        agent_id: str,
        patch: AgentPatch,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentSpec:
        return await save_agent_draft(agent_id, patch, tenant, current)

    @app.post(
        "/api/v1/agents/{agent_id}/publish",
        response_model=AgentRevisionInfo,
        dependencies=protected,
    )
    async def publish_agent(
        agent_id: str,
        request: AgentPublishRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentRevisionInfo:
        spec = await current.repository.get_agent(tenant, agent_id)
        if spec is None:
            raise HTTPException(status_code=404, detail="agent not found")
        if spec.revision != request.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"expected latest revision {request.expected_revision}; current is {spec.revision}",
            )
        current.registry.validate_agent_spec(spec)
        await validate_model_config_reference(
            current, tenant, spec.model.model_config_id, spec.model.config
        )
        try:
            await current.repository.publish_agent(
                tenant,
                agent_id,
                request.expected_revision,
            )
        except RecordNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        record = await current.repository.get_agent_revision_info(
            tenant, agent_id, request.expected_revision
        )
        if record is None:
            raise HTTPException(status_code=404, detail="agent revision not found")
        return record

    @app.post(
        "/api/v1/agents/{agent_id}/rollback",
        response_model=AgentRevisionInfo,
        dependencies=protected,
    )
    async def rollback_agent(
        agent_id: str,
        request: AgentRollbackRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> AgentRevisionInfo:
        target = await current.repository.get_agent(tenant, agent_id, request.revision)
        if target is None:
            raise HTTPException(status_code=404, detail="agent revision not found")
        current.registry.validate_agent_spec(target)
        await validate_model_config_reference(
            current, tenant, target.model.model_config_id, target.model.config
        )
        try:
            await current.repository.rollback_agent(
                tenant,
                agent_id,
                request.revision,
                expected_revision=request.expected_revision,
            )
        except RecordNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        record = await current.repository.get_agent_revision_info(
            tenant, agent_id, request.revision
        )
        if record is None:
            raise HTTPException(status_code=404, detail="agent revision not found")
        return record

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
        if references:
            raise HTTPException(
                status_code=409,
                detail={"mounted_by": references},
            )
        if not await current.repository.delete_agent(tenant, agent_id):
            raise HTTPException(status_code=404, detail="agent not found")
        return Response(status_code=204)

    @app.get(
        "/api/v1/agents/{agent_id}/revisions",
        response_model=List[AgentRevisionInfo],
        dependencies=protected,
    )
    async def list_revisions(
        agent_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> List[AgentRevisionInfo]:
        if await current.repository.get_agent(tenant, agent_id) is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return await current.repository.list_agent_revision_infos(tenant, agent_id)

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

    @app.get(
        "/api/v1/runs/{run_id}/plan",
        response_model=ExecutionPlan,
        dependencies=protected,
    )
    async def get_plan(
        run_id: str,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ExecutionPlan:
        run = await current.repository.get_run(tenant, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        if run.plan is None:
            raise HTTPException(status_code=404, detail="run has no plan")
        return run.plan

    @app.patch(
        "/api/v1/runs/{run_id}/plan",
        response_model=ExecutionPlan,
        dependencies=protected,
    )
    async def edit_plan(
        run_id: str,
        plan_request: PlanEditRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ExecutionPlan:
        try:
            return await current.runs.edit_plan(tenant, run_id, plan_request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runs/{run_id}/plan/approve",
        response_model=RunRecord,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=protected,
    )
    async def approve_plan(
        run_id: str,
        approval: PlanApprovalRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> RunRecord:
        try:
            return await current.runs.approve_plan(tenant, run_id, approval.expected_version)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runs/{run_id}/plan/reject",
        response_model=ExecutionPlan,
        dependencies=protected,
    )
    async def reject_plan(
        run_id: str,
        approval: PlanApprovalRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> ExecutionPlan:
        try:
            return await current.runs.reject_plan(tenant, run_id, approval.expected_version)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runs/{run_id}/choice",
        response_model=RunRecord,
        dependencies=protected,
    )
    async def resolve_choice(
        run_id: str,
        choice_request: ChoiceResolutionRequest,
        tenant: str = Depends(tenant_id),
        current: Container = Depends(get_container),
    ) -> RunRecord:
        try:
            return await current.runs.resolve_choice(tenant, run_id, choice_request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
