import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.rag_query_service import RagQueryService
from app.core.security import decode_refresh_token
from app.core.settings import Settings, get_settings
from app.domain.models import UserRole
from app.infrastructure.database import get_session
from app.interfaces.http.dependencies import (
    AuthContextDependency,
    AuthServiceDependency,
    ConfidenceServiceDependency,
    DecompositionConfigServiceDependency,
    IndexProfileServiceDependency,
    IngestionServiceDependency,
    KnowledgeBaseServiceDependency,
    McpRuntimeServiceDependency,
    MemoryConfigServiceDependency,
    ModelProfileServiceDependency,
    PlannerConfigServiceDependency,
    ProviderCredentialServiceDependency,
    RagQueryServiceDependency,
    RagTraceServiceDependency,
    RetrievalConfigServiceDependency,
    TenantContextDependency,
)
from app.interfaces.http.schemas import (
    CompleteIntakeRequest,
    ConfidenceConfigUpdateRequest,
    CreateDecompositionConfigRequest,
    CreateIndexProfileRequest,
    CreateIntakeRequest,
    CreateKnowledgeBaseRequest,
    CreateMcpServerRequest,
    CreateMemoryConfigRequest,
    CreateModelProfileRequest,
    CreatePlannerConfigRequest,
    InvokeToolRequest,
    LoginRequest,
    ParsedTextResponse,
    RagAnswerFeedbackRequest,
    RagQueryRequest,
    RegisterRequest,
    RetrievalConfigRequest,
    RetrievalConfigResponse,
    SetProviderCredentialRequest,
    SuccessEnvelope,
    UpdateMcpToolRequest,
    UpdateParsedTextRequest,
    LabelRequest,
    BulkLabelRequest,
    CalibrateRequest,
    PromoteRequest,
    GenerateSyntheticRequest,
)

system_router = APIRouter(tags=["System"])
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
rag_router = APIRouter(prefix="/rag", tags=["RAG Ingestion"])
rag_query_router = APIRouter(prefix="/rag/query", tags=["RAG Query"])
kb_router = APIRouter(prefix="/rag/knowledge-bases", tags=["Knowledge Bases"])
model_profile_router = APIRouter(prefix="/rag/model-profiles", tags=["Model Profiles"])
index_profile_router = APIRouter(prefix="/rag/index-profiles", tags=["Index Profiles"])
provider_credential_router = APIRouter(prefix="/rag/provider-credentials", tags=["Provider Credentials"])
mcp_router = APIRouter(prefix="/rag/mcp", tags=["MCP Runtime"])
confidence_router = APIRouter(prefix="/confidence", tags=["confidence"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])


def success(message: str, data: object | None = None, meta: object | None = None) -> dict[str, object]:
    response: dict[str, object] = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    if meta is not None:
        response["meta"] = meta
    return response


@confidence_router.get(
    "/config/{profile_id}",
    summary="Get confidence configuration",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}},
)
async def get_confidence_config(
    profile_id: str,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
) -> dict[str, object]:
    """Return the persisted profile config or safe defaults in the active tenant."""
    return success("Confidence configuration loaded", await service.get_config(tenant=tenant, profile_id=profile_id))


@confidence_router.patch(
    "/config/{profile_id}",
    summary="Update confidence configuration",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}, 422: {"description": "Invalid configuration or missing active model"}},
)
async def update_confidence_config(
    profile_id: str,
    payload: ConfidenceConfigUpdateRequest,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
) -> dict[str, object]:
    return success(
        "Confidence configuration updated",
        await service.update_config(tenant=tenant, profile_id=profile_id, **payload.model_dump()),
    )


@confidence_router.get(
    "/fixtures",
    summary="List calibration fixtures",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}},
)
async def list_calibration_fixtures(
    profile_id: str,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
) -> dict[str, object]:
    return success("Calibration fixtures loaded", await service.list_fixtures(tenant=tenant, profile_id=profile_id))


@confidence_router.post(
    "/fixtures/import",
    summary="Import calibration fixture from CSV",
    response_model=SuccessEnvelope,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"description": "Tenant scope mismatch"}, 422: {"description": "Invalid CSV"}},
)
async def import_calibration_fixture(
    profile_id: str,
    version: str,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> dict[str, object]:
    from app.application.calibration_service import import_calibration_fixture as _import
    from app.infrastructure.rag_catalog import SqlCalibrationFixtureRepository
    from app.infrastructure.rag_answer_trace import SqlAlchemyAnswerRunRepository
    from app.domain.rag.repositories import ChunkRepository

    class _NullChunkRepo:
        async def find_by_ids(self, *, tenant_id: str, chunk_ids: tuple[str, ...]) -> list[object]:
            return []

    content = (await file.read()).decode("utf-8")
    fixtures = SqlCalibrationFixtureRepository(session)
    result = await _import(
        fixtures,
        _NullChunkRepo(),  # type: ignore[arg-type]
        tenant_id=tenant.tenant_id,
        retrieval_profile_id=profile_id,
        created_by=tenant.user_id,
        version=version,
        csv_content=content,
    )
    return success(
        "Fixture imported",
        {
            "fixtureId": result.fixture.id,
            "importedEntries": result.imported_entries,
            "version": result.fixture.version,
        },
    )


@confidence_router.post(
    "/fixtures/generate-synthetic",
    summary="Enqueue synthetic fixture generation",
    response_model=SuccessEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    responses={403: {"description": "Tenant scope mismatch"}},
)
async def generate_synthetic_fixture(
    profile_id: str,
    payload: GenerateSyntheticRequest,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    from uuid import uuid4

    trace_id = str(uuid4())
    job_id = await service.enqueue_synthetic(
        tenant=tenant,
        profile_id=profile_id,
        knowledge_base_id=payload.knowledge_base_id,
        count=payload.count,
        trace_id=trace_id,
        redis_url=settings.redis_url,
    )
    return success("Synthetic fixture generation enqueued", {"jobId": job_id})


@confidence_router.get(
    "/fixtures/{fixture_id}/entries",
    summary="List fixture entries",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}, 404: {"description": "Fixture not found"}},
)
async def list_fixture_entries(
    fixture_id: str,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, object]:
    items = await service.get_fixture_entries(
        tenant=tenant,
        fixture_id=fixture_id,
        page=max(1, page),
        page_size=min(max(1, page_size), 200),
    )
    return success("Fixture entries loaded", {"items": items, "page": page, "pageSize": page_size})


@confidence_router.get(
    "/answer-runs/unlabeled",
    summary="List unlabeled answer runs",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}},
)
async def list_unlabeled_answer_runs(
    profile_id: str,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, object]:
    items = await service.get_unlabeled_runs(
        tenant=tenant,
        profile_id=profile_id,
        page=max(1, page),
        page_size=min(max(1, page_size), 200),
    )
    return success("Unlabeled answer runs loaded", {"items": items, "page": page, "pageSize": page_size})


@confidence_router.post(
    "/fixtures/{fixture_id}/label",
    summary="Label a single answer run",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}, 422: {"description": "Invalid label or missing feature vector"}},
)
async def label_answer_run(
    fixture_id: str,
    payload: LabelRequest,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
) -> dict[str, object]:
    count = await service.label_run(
        tenant=tenant,
        fixture_id=fixture_id,
        answer_run_id=payload.answer_run_id,
        label=payload.label,
        annotator_id=tenant.user_id,
    )
    return success("Answer run labeled", {"labeled": count})


@confidence_router.post(
    "/fixtures/{fixture_id}/label-bulk",
    summary="Bulk label answer runs",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}, 422: {"description": "Invalid labels or missing feature vectors"}},
)
async def bulk_label_answer_runs(
    fixture_id: str,
    payload: BulkLabelRequest,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
) -> dict[str, object]:
    count = await service.bulk_label_runs(
        tenant=tenant,
        fixture_id=fixture_id,
        labels=payload.labels,
        annotator_id=tenant.user_id,
    )
    return success("Answer runs labeled", {"labeled": count})


@confidence_router.post(
    "/calibrate/{profile_id}",
    summary="Enqueue calibration job",
    response_model=SuccessEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        403: {"description": "Tenant scope mismatch"},
        422: {"description": "Insufficient labeled entries"},
    },
)
async def enqueue_calibration(
    profile_id: str,
    payload: CalibrateRequest,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    from uuid import uuid4

    trace_id = str(uuid4())
    job_id = await service.enqueue_calibration(
        tenant=tenant,
        profile_id=profile_id,
        fixture_id=payload.fixture_id,
        trace_id=trace_id,
        redis_url=settings.redis_url,
    )
    return success("Calibration job enqueued", {"jobId": job_id})


@confidence_router.get(
    "/calibrate/{job_id}/status",
    summary="Poll calibration job status",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}},
)
async def get_calibration_status(
    job_id: str,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    result = await service.get_calibration_status(job_id=job_id, redis_url=settings.redis_url)
    return success("Calibration status loaded", result)


@confidence_router.get(
    "/models/{model_version_id}/threshold",
    summary="Evaluate threshold metrics",
    response_model=SuccessEnvelope,
    responses={403: {"description": "Tenant scope mismatch"}, 404: {"description": "Model version not found"}},
)
async def evaluate_threshold(
    model_version_id: str,
    threshold: float,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
) -> dict[str, object]:
    result = await service.evaluate_threshold(
        tenant=tenant,
        model_version_id=model_version_id,
        threshold=threshold,
    )
    return success("Threshold evaluated", result)


@confidence_router.post(
    "/models/{model_version_id}/promote",
    summary="Promote a calibration model",
    response_model=SuccessEnvelope,
    responses={
        403: {"description": "Tenant scope mismatch"},
        404: {"description": "Model version not found"},
        422: {"description": "Synthetic-only emit lock"},
    },
)
async def promote_model(
    model_version_id: str,
    payload: PromoteRequest,
    tenant: TenantContextDependency,
    service: ConfidenceServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    result = await service.promote_model(
        tenant=tenant,
        model_version_id=model_version_id,
        promoted_by=payload.promoted_by or tenant.user_id,
        redis_url=settings.redis_url,
    )
    return success("Model promoted", result)


# --- Internal endpoints (called by Node worker) ----------------------------


def _validate_internal_secret(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    secret = request.headers.get("X-Internal-Secret", "")
    if not secret or secret != settings.internal_api_secret:
        from app.domain.errors import DomainError
        raise DomainError.forbidden("Invalid internal secret")


@internal_router.post(
    "/confidence/calibrate",
    summary="Run calibration (internal)",
    response_model=SuccessEnvelope,
    include_in_schema=False,
)
async def internal_run_calibration(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    _validate_internal_secret(request, settings)
    body = await request.json()
    tenant_id = str(body.get("tenant_id", ""))
    profile_id = str(body.get("profile_id", ""))
    fixture_id = str(body.get("fixture_id", ""))
    if not tenant_id or not profile_id or not fixture_id:
        from app.domain.errors import DomainError
        raise DomainError("VALIDATION", "tenant_id, profile_id, fixture_id required", 422)

    from app.application.calibration_service import CalibrationRunner, precision_recall_svg
    from app.infrastructure.rag_answer_trace import SqlAlchemyAnswerRunRepository
    from app.infrastructure.rag_catalog import (
        SqlCalibrationFixtureRepository,
        SqlCalibrationModelRepository,
        SqlConfidenceConfigRepository,
    )

    class _S3ArtifactStore:
        def __init__(self, s: Settings) -> None:
            self._settings = s

        async def put(self, *, path: str, data: bytes) -> None:
            import pathlib
            if self._settings.object_store_local_path:
                dest = pathlib.Path(self._settings.object_store_local_path) / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                return
            import aioboto3  # type: ignore
            s3_session = aioboto3.Session()
            async with s3_session.client(
                "s3",
                endpoint_url=self._settings.object_store_endpoint,
                aws_access_key_id=self._settings.object_store_access_key,
                aws_secret_access_key=self._settings.object_store_secret_key,
                region_name=self._settings.object_store_region,
            ) as s3:
                await s3.put_object(Bucket=self._settings.object_store_bucket, Key=path, Body=data)

    runner = CalibrationRunner(
        SqlCalibrationFixtureRepository(session),
        SqlAlchemyAnswerRunRepository(session),
        SqlCalibrationModelRepository(session),
        _S3ArtifactStore(settings),
        SqlConfidenceConfigRepository(session),
    )
    result = await runner.run(tenant_id=tenant_id, retrieval_profile_id=profile_id, fixture_id=fixture_id)
    svg = precision_recall_svg(result.curve, result.model.threshold_used)
    return success(
        "Calibration complete",
        {
            "model_version_id": result.model.id,
            "pr_curve_svg": svg,
            "f1_optimal_threshold": result.model.threshold_used,
        },
    )


@internal_router.post(
    "/confidence/fixtures/generate-synthetic",
    summary="Generate synthetic fixture (internal)",
    response_model=SuccessEnvelope,
    include_in_schema=False,
)
async def internal_generate_synthetic(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    _validate_internal_secret(request, settings)
    body = await request.json()
    tenant_id = str(body.get("tenant_id", ""))
    profile_id = str(body.get("profile_id", ""))
    kb_id = str(body.get("kb_id", ""))
    count = int(body.get("count", 50))
    if not tenant_id or not profile_id or not kb_id:
        from app.domain.errors import DomainError
        raise DomainError("VALIDATION", "tenant_id, profile_id, kb_id required", 422)

    from app.application.calibration_service import generate_synthetic_fixture

    class _NullChunkSource:
        async def sample(self, *, tenant_id: str, knowledge_base_id: str, count: int) -> list[tuple[str, str]]:
            return []

    class _NullPairGenerator:
        async def generate(self, *, chunk_text: str, profile_id: str) -> tuple[str, str]:
            return ("", "")

    from app.infrastructure.rag_catalog import SqlCalibrationFixtureRepository

    fixture = await generate_synthetic_fixture(
        SqlCalibrationFixtureRepository(session),
        _NullChunkSource(),  # type: ignore[arg-type]
        _NullPairGenerator(),  # type: ignore[arg-type]
        tenant_id=tenant_id,
        retrieval_profile_id=profile_id,
        knowledge_base_id=kb_id,
        count=count,
        created_by="worker",
    )
    return success("Synthetic fixture generated", {"fixture_id": fixture.id, "entryCount": fixture.entry_count})


@mcp_router.post("/servers", status_code=status.HTTP_201_CREATED)
async def register_mcp_server(payload: CreateMcpServerRequest, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP server registered", await service.register_server(tenant=tenant, **payload.model_dump()))


@mcp_router.get("/servers")
async def list_mcp_servers(tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP servers loaded", await service.list_servers(tenant=tenant))


@mcp_router.get("/servers/{server_id}")
async def get_mcp_server(server_id: str, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP server loaded", await service.get_server(tenant=tenant, server_id=server_id))


@mcp_router.put("/servers/{server_id}")
async def update_mcp_server(server_id: str, payload: CreateMcpServerRequest, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP server updated", await service.update_server(tenant=tenant, server_id=server_id, **payload.model_dump(exclude_unset=True)))


@mcp_router.delete("/servers/{server_id}")
async def delete_mcp_server(server_id: str, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    await service.delete_server(tenant=tenant, server_id=server_id)
    return success("MCP server deleted")


@mcp_router.post("/servers/{server_id}/test")
async def test_mcp_server(server_id: str, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP connection tested", await service.test_connection(tenant=tenant, server_id=server_id))


@mcp_router.post("/servers/{server_id}/discover")
async def discover_mcp_tools(server_id: str, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP tools discovered", await service.discover_tools(tenant=tenant, server_id=server_id))


@mcp_router.get("/servers/{server_id}/tools")
async def list_mcp_tools(server_id: str, tenant: TenantContextDependency, service: McpRuntimeServiceDependency, include_stale: bool = False) -> dict[str, object]:
    return success("MCP tools loaded", await service.list_tools(tenant=tenant, server_id=server_id, include_stale=include_stale))


@mcp_router.put("/tools/{tool_id}")
async def update_mcp_tool(tool_id: str, payload: UpdateMcpToolRequest, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP tool permission updated", await service.set_tool_allowed(tenant=tenant, tool_id=tool_id, allowed=payload.allowed))


@mcp_router.post("/tools/{tool_id}/invoke")
async def invoke_mcp_tool(tool_id: str, payload: InvokeToolRequest, tenant: TenantContextDependency, service: McpRuntimeServiceDependency) -> dict[str, object]:
    return success("MCP tool invoked", await service.invoke_tool(tenant=tenant, tool_id=tool_id, arguments=payload.arguments))


@mcp_router.get("/invocations")
async def list_mcp_invocations(
    tenant: TenantContextDependency,
    service: McpRuntimeServiceDependency,
    server_id: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = 100,
) -> dict[str, object]:
    items = await service.list_invocations(
        tenant=tenant,
        server_id=server_id,
        status=status,
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
        limit=min(max(limit, 1), 100),
    )
    return success("MCP invocations loaded", {"items": items, "total": len(items)})


@system_router.get("/")
async def get_app_info() -> dict[str, object]:
    return success("Application info loaded", {"name": "open-grounding-api", "message": "FastAPI clean architecture API is ready"})


@system_router.get("/ready")
async def get_readiness(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    """Readiness diagnostic for RAG platform dependencies.

    Reports PostgreSQL, Redis, Qdrant, object storage, deployment tenant, and
    active index-profile availability without exposing credentials, internal
    URLs, or raw provider errors. This is not a retrieval endpoint.
    """
    from app.infrastructure.rag_health import build_readiness_report

    report = await build_readiness_report(settings)
    status_code_label = "ready" if report.status == "ready" else "degraded"
    return success(f"Readiness {status_code_label}", report.to_dict())


@system_router.get("/health")
async def get_health(request: Request) -> dict[str, object]:
    from datetime import UTC, datetime

    from app.core.settings import get_settings
    from app.infrastructure.tenant_bootstrap import tenant_diagnostics

    bootstrap_result = getattr(request.app.state, "tenant_bootstrap_result", None)
    return success(
        "Health status loaded",
        {
            "status": "ok",
            "service": "open-grounding-api",
            "timestamp": datetime.now(UTC).isoformat(),
            "tenant": tenant_diagnostics(get_settings(), bootstrap_result),
        },
    )


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success("Register success", await service.register(name=payload.name, email=str(payload.email), password=payload.password))


@auth_router.post("/login")
async def login(payload: LoginRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success("Login success", await service.login(email=str(payload.email), password=payload.password))


@auth_router.post("/logout")
async def logout(context: AuthContextDependency, service: AuthServiceDependency) -> dict[str, object]:
    await service.logout(user_id=context["id"], session_id=context["sessionId"], access_token=context["accessToken"])
    return success("Logout success", {"success": True})


@auth_router.get("/me")
async def current_user(context: AuthContextDependency, service: AuthServiceDependency) -> dict[str, object]:
    return success("Current user loaded", await service.current_user(user_id=context["id"], session_id=context["sessionId"]))


@auth_router.post("/refresh")
async def refresh(
    service: AuthServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        from app.domain.errors import DomainError

        raise DomainError.unauthorized()
    refresh_token = authorization.removeprefix("Bearer ").strip()
    decode_refresh_token(refresh_token, settings)
    return success("Token refreshed", await service.refresh(refresh_token))


@auth_router.get("/tenant/context")
async def get_tenant_context(tenant: TenantContextDependency) -> dict[str, object]:
    """Return the server-derived tenant context for the authenticated user.

    This endpoint proves that tenant context is resolved from deployment
    configuration and authenticated membership — never from client-supplied
    headers, path, query, body, or JWT claims.
    """
    return success(
        "Tenant context loaded",
        {"tenantId": tenant.tenant_id, "membershipId": tenant.membership_id, "userId": tenant.user_id},
    )


# --- RAG ingestion routes -----------------------------------------------------


@rag_router.post("/ingestion/intake", status_code=status.HTTP_201_CREATED)
async def create_intake(
    payload: CreateIntakeRequest,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    """Create a pending document version and return an upload target."""
    result = await service.create_intake(
        tenant=tenant,
        knowledge_base_id=payload.knowledge_base_id,
        filename=payload.filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        title=payload.title,
        source_revision=payload.source_revision,
        metadata=payload.metadata,
    )
    return success(
        "Intake created",
        {
            "documentId": result.document_id,
            "documentVersionId": result.document_version_id,
            "uploadKey": result.upload_key,
            "expiresIn": 3600,
        },
    )


@rag_router.put("/ingestion/upload/{document_version_id}", status_code=status.HTTP_200_OK)
async def upload_document(
    document_version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> dict[str, object]:
    """Upload document file to object store."""
    import aioboto3  # type: ignore

    version = await service._version_repo.find_by_id(
        tenant_id=tenant.tenant_id,
        version_id=document_version_id,
    )
    if version is None:
        from app.domain.errors import DomainError

        raise DomainError("VERSION_NOT_FOUND", "Document version not found", 404)

    content = await file.read()
    bucket = settings.object_store_bucket
    s3_session = aioboto3.Session()
    async with s3_session.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
        region_name="us-east-1",
    ) as s3:
        await s3.put_object(
            Bucket=bucket,
            Key=version.object_key_raw,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )

    return success("File uploaded", {"documentVersionId": document_version_id})


@rag_router.post("/ingestion/complete")
async def complete_intake(
    payload: CompleteIntakeRequest,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    """Validate upload completion and transition to STORED."""
    result = await service.complete_intake(
        tenant=tenant,
        document_version_id=payload.document_version_id,
        content_checksum=payload.content_checksum,
    )
    return success(
        "Intake completed",
        {
            "documentVersionId": result.document_version_id,
            "lifecycleState": result.lifecycle_state,
            "enqueued": result.enqueued,
        },
    )


@rag_router.get("/ingestion/documents")
async def list_documents(
    knowledge_base_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    """List document versions for a knowledge base."""
    rows = await service._version_repo.list_by_knowledge_base(
        tenant_id=tenant.tenant_id,
        knowledge_base_id=knowledge_base_id,
    )
    return success(
        "Documents loaded",
        [
            {
                "documentVersionId": ver.id,
                "documentId": doc_id,
                "title": title,
                "lifecycleState": ver.lifecycle_state.value,
                "mimeType": ver.mime_type,
                "sizeBytes": ver.size_bytes,
                "createdAt": ver.created_at.isoformat() if ver.created_at else None,
            }
            for ver, title, doc_id in rows
        ],
    )


@rag_router.get("/ingestion/pending-review/count")
async def get_pending_review_count(
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    """Return count of document versions in NEEDS_REVIEW state for the tenant."""
    count = await service.get_pending_review_count(tenant=tenant)
    return success("Pending review count", {"count": count})


@rag_router.get(
    "/ingestion/{version_id}/parsed-text",
    summary="Get parsed text for a document version",
    response_model=None,
)
async def get_parsed_text(
    version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    version = await service._version_repo.find_by_id(tenant_id=tenant.tenant_id, version_id=version_id)
    if version is None:
        from app.domain.errors import DomainError
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    return success(
        "Parsed text loaded",
        {
            "versionId": version.id,
            "parsedText": version.parsed_text,
            "lifecycleState": version.lifecycle_state.value,
        },
    )


@rag_router.patch(
    "/ingestion/{version_id}/parsed-text",
    summary="Update parsed text for a document version",
    response_model=None,
)
async def update_parsed_text(
    version_id: str,
    payload: UpdateParsedTextRequest,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    from app.domain.errors import DomainError
    from app.domain.rag.catalog import DocumentVersionLifecycleState

    version = await service._version_repo.find_by_id(tenant_id=tenant.tenant_id, version_id=version_id)
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    if version.lifecycle_state != DocumentVersionLifecycleState.NEEDS_REVIEW:
        raise DomainError("CONFLICT", "Version is not in NEEDS_REVIEW state", 409)
    updated = await service._version_repo.patch_parsed_text(
        tenant_id=tenant.tenant_id, version_id=version_id, text=payload.text
    )
    return success(
        "Parsed text updated",
        {
            "versionId": updated.id,
            "parsedText": updated.parsed_text,
            "lifecycleState": updated.lifecycle_state.value,
        },
    )


@rag_router.post(
    "/ingestion/{version_id}/approve",
    summary="Approve parsed text and trigger chunking",
    response_model=None,
)
async def approve_parsed_text(
    version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    from app.domain.errors import DomainError
    from app.domain.rag.catalog import DocumentVersionLifecycleState

    version = await service._version_repo.find_by_id(tenant_id=tenant.tenant_id, version_id=version_id)
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    if version.lifecycle_state != DocumentVersionLifecycleState.NEEDS_REVIEW:
        raise DomainError("CONFLICT", "Version is not in NEEDS_REVIEW state", 409)
    updated = await service._version_repo.update_lifecycle_state(
        tenant_id=tenant.tenant_id,
        version_id=version_id,
        lifecycle_state="NORMALIZING",
    )
    enqueued = await service._enqueue_chunking(tenant=tenant, version=updated)
    return success(
        "Document version approved",
        {
            "versionId": updated.id,
            "lifecycleState": updated.lifecycle_state.value,
            "enqueued": enqueued,
        },
    )


@rag_router.post(
    "/ingestion/{version_id}/reject",
    summary="Reject parsed text and fail the document version",
    response_model=None,
)
async def reject_parsed_text(
    version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    from app.domain.errors import DomainError
    from app.domain.rag.catalog import DocumentVersionLifecycleState

    version = await service._version_repo.find_by_id(tenant_id=tenant.tenant_id, version_id=version_id)
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    if version.lifecycle_state != DocumentVersionLifecycleState.NEEDS_REVIEW:
        raise DomainError("CONFLICT", "Version is not in NEEDS_REVIEW state", 409)
    updated = await service._version_repo.update_lifecycle_state(
        tenant_id=tenant.tenant_id,
        version_id=version_id,
        lifecycle_state="FAILED",
    )
    return success(
        "Document version rejected",
        {"versionId": updated.id, "lifecycleState": updated.lifecycle_state.value},
    )


@rag_router.get("/ingestion/status/{document_version_id}")
async def get_ingestion_status(
    document_version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    """Return tenant-scoped ingestion status for a document version."""
    status_data = await service.get_status(
        tenant=tenant,
        document_version_id=document_version_id,
    )
    return success("Ingestion status loaded", status_data)


@rag_router.delete("/ingestion/{document_version_id}")
async def delete_version(
    document_version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    """Soft-delete a document version (removes from active retrieval)."""
    await service.soft_delete(tenant=tenant, document_version_id=document_version_id)
    return success("Document version scheduled for deletion")


@rag_query_router.post(
    "",
    summary="Query permitted RAG evidence",
    description="Uses only server-derived tenant and authorization scope. Set stream=true for text/event-stream.",
    response_model=None,
)
async def query_rag(
    payload: RagQueryRequest,
    tenant: TenantContextDependency,
    service: RagQueryServiceDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object] | StreamingResponse:
    decomposition_enabled = payload.decomposition.enabled if payload.decomposition else None
    decomposition_max_sub_queries = payload.decomposition.max_sub_queries if payload.decomposition else None
    planner_enabled = payload.planner.enabled if payload.planner else None
    planner_max_tasks = payload.planner.max_tasks if payload.planner else None
    planner_task_types = tuple(payload.planner.task_types) if payload.planner and payload.planner.task_types else None
    memory_enabled = payload.memory.enabled if payload.memory else None
    if payload.stream:
        return StreamingResponse(
            _stream_query(
                service,
                tenant=tenant,
                message=payload.message,
                knowledge_base_ids=tuple(payload.knowledge_base_ids),
                conversation_id=payload.conversation_id,
                decomposition_enabled=decomposition_enabled,
                decomposition_max_sub_queries=decomposition_max_sub_queries,
                planner_enabled=planner_enabled,
                planner_max_tasks=planner_max_tasks,
                planner_task_types=planner_task_types,
                memory_enabled=memory_enabled,
                session=session,
            ),
            media_type="text/event-stream",
        )
    result = await service.query(
        tenant=tenant,
        message=payload.message,
        knowledge_base_ids=tuple(payload.knowledge_base_ids),
        conversation_id=payload.conversation_id,
        decomposition_enabled=decomposition_enabled,
        decomposition_max_sub_queries=decomposition_max_sub_queries,
        planner_enabled=planner_enabled,
        planner_max_tasks=planner_max_tasks,
        planner_task_types=planner_task_types,
        memory_enabled=memory_enabled,
        session=session,
    )
    return success("Query completed", result)


@rag_query_router.get(
    "/traces/{trace_id}",
    summary="Inspect a retained RAG answer trace",
    description="Requires tenant ADMIN access. Expired and cross-tenant traces are not disclosed.",
    responses={403: {"description": "Operator access required"}, 404: {"description": "Trace is unavailable or expired"}},
)
async def get_rag_trace(
    trace_id: str,
    tenant: TenantContextDependency,
    service: RagTraceServiceDependency,
) -> dict[str, object]:
    return success("Answer trace loaded", await service.get_trace(tenant=tenant, trace_id=trace_id))


@rag_query_router.post(
    "/traces/{trace_id}/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Record answer feedback",
    description="Records tenant-scoped feedback only while the referenced trace is retained.",
    responses={404: {"description": "Trace is unavailable or expired"}},
)
async def create_rag_feedback(
    trace_id: str,
    payload: RagAnswerFeedbackRequest,
    tenant: TenantContextDependency,
    service: RagTraceServiceDependency,
) -> dict[str, object]:
    return success(
        "Answer feedback recorded",
        await service.create_feedback(tenant=tenant, trace_id=trace_id, rating=payload.rating, comment=payload.comment),
    )


async def _stream_query(
    service: RagQueryService,
    *,
    tenant: TenantContextDependency,
    message: str,
    knowledge_base_ids: tuple[str, ...],
    conversation_id: str | None,
    decomposition_enabled: bool | None = None,
    decomposition_max_sub_queries: int | None = None,
    planner_enabled: bool | None = None,
    planner_max_tasks: int | None = None,
    planner_task_types: tuple[str, ...] | None = None,
    memory_enabled: bool | None = None,
    session: AsyncSession,
) -> AsyncIterator[str]:
    try:
        result = await service.query(
            tenant=tenant,
            message=message,
            knowledge_base_ids=knowledge_base_ids,
            conversation_id=conversation_id,
            decomposition_enabled=decomposition_enabled,
            decomposition_max_sub_queries=decomposition_max_sub_queries,
            planner_enabled=planner_enabled,
            planner_max_tasks=planner_max_tasks,
            planner_task_types=planner_task_types,
            memory_enabled=memory_enabled,
            session=session,
        )
    except Exception:
        yield _sse_event("response.failed", {"code": "QUERY_FAILED"})
        return

    trace_id = result["traceId"]
    yield _sse_event("response.started", {"traceId": trace_id, "conversationId": result.get("conversationId")})
    yield _sse_event("response.route", {"route": result["route"]})

    # tool_call and tool_result events — emitted only when route is "tool"
    for tool_event in result.get("toolCalls", []):
        yield _sse_event(
            "response.tool_call",
            {
                "toolSlug": tool_event.get("toolSlug"),
                "inputHash": tool_event.get("inputHash"),
                "traceId": trace_id,
            },
        )
        yield _sse_event(
            "response.tool_result",
            {
                "toolSlug": tool_event.get("toolSlug"),
                "evidenceCount": tool_event.get("evidenceCount", 0),
                "latencyMs": tool_event.get("latencyMs"),
                "status": tool_event.get("status"),
            },
        )

    yield _sse_event("response.retrieval_summary", {"evidenceLevel": result["evidenceLevel"]})
    if result["answer"] is not None:
        yield _sse_event("response.delta", {"answer": result["answer"]})
    yield _sse_event("response.citations", {"citations": result["citations"]})
    yield _sse_event(
        "response.completed",
        {
            "traceId": trace_id,
            "evidenceLevel": result["evidenceLevel"],
            "limitations": result["limitations"],
        },
    )


def _sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


# --- Knowledge base routes ---------------------------------------------------


@kb_router.post("", status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: CreateKnowledgeBaseRequest,
    kb_service: KnowledgeBaseServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Create a new tenant-scoped knowledge base."""
    result = await kb_service.create(
        tenant=tenant,
        name=payload.name,
        slug=payload.slug,
    )
    return success(
        "Knowledge base created",
        {
            "id": result.id,
            "tenantId": result.tenant_id,
            "slug": result.slug,
            "name": result.name,
            "status": result.status,
            "createdAt": result.created_at,
            "updatedAt": result.updated_at,
        },
    )


@kb_router.get("")
async def list_knowledge_bases(
    kb_service: KnowledgeBaseServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """List all active knowledge bases for the authenticated tenant."""
    results = await kb_service.list_all(tenant=tenant)
    return success(
        "Knowledge bases loaded",
        [
            {
                "id": r.id,
                "tenantId": r.tenant_id,
                "slug": r.slug,
                "name": r.name,
                "status": r.status,
                "createdAt": r.created_at,
                "updatedAt": r.updated_at,
            }
            for r in results
        ],
    )


@kb_router.delete("/{knowledge_base_id}", status_code=status.HTTP_200_OK)
async def delete_knowledge_base(
    knowledge_base_id: str,
    kb_service: KnowledgeBaseServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Soft-delete (archive) a knowledge base."""
    result = await kb_service.archive(
        tenant=tenant,
        knowledge_base_id=knowledge_base_id,
    )
    return success(
        "Knowledge base archived",
        {
            "id": result.id,
            "status": result.status,
        },
    )


# --- Decomposition config routes --------------------------------------------


@kb_router.post("/{knowledge_base_id}/decomposition", status_code=status.HTTP_200_OK)
async def upsert_decomposition_config(
    knowledge_base_id: str,
    payload: CreateDecompositionConfigRequest,
    svc: DecompositionConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Create or replace decomposition config for a knowledge base."""
    result = await svc.upsert(
        tenant=tenant,
        knowledge_base_id=knowledge_base_id,
        enabled=payload.enabled,
        model_profile_id=payload.model_profile_id,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
        max_sub_queries=payload.max_sub_queries,
        max_depth=payload.max_depth,
        min_complexity_score=payload.min_complexity_score,
        guardrails=payload.guardrails,
    )
    return success("Decomposition config saved", _decomposition_config_dto(result))


@kb_router.get("/{knowledge_base_id}/decomposition")
async def get_decomposition_config(
    knowledge_base_id: str,
    svc: DecompositionConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Get decomposition config for a knowledge base."""
    from app.domain.errors import DomainError

    result = await svc.get(tenant=tenant, knowledge_base_id=knowledge_base_id)
    if result is None:
        raise DomainError("NOT_FOUND", "Decomposition config not found", 404)
    return success("Decomposition config loaded", _decomposition_config_dto(result))


@kb_router.delete("/{knowledge_base_id}/decomposition", status_code=status.HTTP_200_OK)
async def delete_decomposition_config(
    knowledge_base_id: str,
    svc: DecompositionConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Delete decomposition config for a knowledge base."""
    deleted = await svc.delete(tenant=tenant, knowledge_base_id=knowledge_base_id)
    if not deleted:
        from app.domain.errors import DomainError

        raise DomainError("NOT_FOUND", "Decomposition config not found", 404)
    return success("Decomposition config deleted")


@kb_router.get("/{knowledge_base_id}/decomposition/defaults")
async def get_decomposition_defaults(
    knowledge_base_id: str,
    svc: DecompositionConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Get default decomposition config values."""
    return success("Decomposition defaults loaded", svc.get_defaults())


@kb_router.post("/{knowledge_base_id}/planner", status_code=status.HTTP_200_OK)
async def upsert_planner_config(
    knowledge_base_id: str,
    payload: CreatePlannerConfigRequest,
    svc: PlannerConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await svc.upsert(
        tenant=tenant,
        knowledge_base_id=knowledge_base_id,
        enabled=payload.enabled,
        model_profile_id=payload.model_profile_id,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
        max_tasks=payload.max_tasks,
        task_timeout_seconds=payload.task_timeout_seconds,
        task_types=payload.task_types,
        mcp_enabled=payload.mcp_enabled,
        guardrails=payload.guardrails,
    )
    return success("Planner config saved", _planner_config_dto(result))


@kb_router.get("/{knowledge_base_id}/planner")
async def get_planner_config(
    knowledge_base_id: str,
    svc: PlannerConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    from app.domain.errors import DomainError

    result = await svc.get(tenant=tenant, knowledge_base_id=knowledge_base_id)
    if result is None:
        raise DomainError("NOT_FOUND", "Planner config not found", 404)
    return success("Planner config loaded", _planner_config_dto(result))


@kb_router.delete("/{knowledge_base_id}/planner", status_code=status.HTTP_200_OK)
async def delete_planner_config(
    knowledge_base_id: str,
    svc: PlannerConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    from app.domain.errors import DomainError

    if not await svc.delete(tenant=tenant, knowledge_base_id=knowledge_base_id):
        raise DomainError("NOT_FOUND", "Planner config not found", 404)
    return success("Planner config deleted")


@kb_router.get("/{knowledge_base_id}/planner/defaults")
async def get_planner_defaults(
    knowledge_base_id: str,
    svc: PlannerConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    return success("Planner defaults loaded", svc.get_defaults())


def _decomposition_config_dto(config: object) -> dict[str, object]:
    return {
        "id": config.id,  # type: ignore[union-attr]
        "knowledgeBaseId": config.knowledge_base_id,  # type: ignore[union-attr]
        "enabled": config.enabled,  # type: ignore[union-attr]
        "modelProfileId": config.model_profile_id,  # type: ignore[union-attr]
        "systemPrompt": config.system_prompt,  # type: ignore[union-attr]
        "userPromptTemplate": config.user_prompt_template,  # type: ignore[union-attr]
        "maxSubQueries": config.max_sub_queries,  # type: ignore[union-attr]
        "maxDepth": config.max_depth,  # type: ignore[union-attr]
        "minComplexityScore": config.min_complexity_score,  # type: ignore[union-attr]
        "guardrails": config.guardrails,  # type: ignore[union-attr]
        "createdAt": config.created_at.isoformat(),  # type: ignore[union-attr]
        "updatedAt": config.updated_at.isoformat(),  # type: ignore[union-attr]
    }


def _planner_config_dto(config: object) -> dict[str, object]:
    return {
        "id": config.id,  # type: ignore[union-attr]
        "knowledgeBaseId": config.knowledge_base_id,  # type: ignore[union-attr]
        "enabled": config.enabled,  # type: ignore[union-attr]
        "modelProfileId": config.model_profile_id,  # type: ignore[union-attr]
        "systemPrompt": config.system_prompt,  # type: ignore[union-attr]
        "userPromptTemplate": config.user_prompt_template,  # type: ignore[union-attr]
        "maxTasks": config.max_tasks,  # type: ignore[union-attr]
        "taskTimeoutSeconds": config.task_timeout_seconds,  # type: ignore[union-attr]
        "taskTypes": list(config.task_types),  # type: ignore[union-attr]
        "mcpEnabled": config.mcp_enabled,  # type: ignore[union-attr]
        "guardrails": config.guardrails,  # type: ignore[union-attr]
        "createdAt": config.created_at.isoformat(),  # type: ignore[union-attr]
        "updatedAt": config.updated_at.isoformat(),  # type: ignore[union-attr]
    }


# --- Model profile routes ---------------------------------------------------


@model_profile_router.post("", status_code=status.HTTP_201_CREATED)
async def create_model_profile(
    payload: CreateModelProfileRequest,
    svc: ModelProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await svc.create(
        tenant=tenant,
        name=payload.name,
        profile_kind=payload.profile_kind,
        provider=payload.provider,
        model=payload.model,
        modality=payload.modality,
        dimensions=payload.dimensions,
        config_json=payload.config_json,
    )
    return success(
        "Model profile created",
        {
            "id": result.id,
            "name": result.name,
            "profileKind": result.profile_kind,
            "provider": result.provider,
            "model": result.model,
            "modality": result.modality,
            "dimensions": result.dimensions,
            "version": result.version,
            "isActive": result.is_active,
            "createdAt": result.created_at,
        },
    )


@model_profile_router.get("")
async def list_model_profiles(
    svc: ModelProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    results = await svc.list_all(tenant=tenant)
    return success(
        "Model profiles loaded",
        [
            {
                "id": r.id,
                "name": r.name,
                "profileKind": r.profile_kind,
                "provider": r.provider,
                "model": r.model,
                "modality": r.modality,
                "dimensions": r.dimensions,
                "version": r.version,
                "isActive": r.is_active,
                "createdAt": r.created_at,
            }
            for r in results
        ],
    )


@model_profile_router.delete("/{profile_id}", status_code=status.HTTP_200_OK)
async def delete_model_profile(
    profile_id: str,
    svc: ModelProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await svc.archive(tenant=tenant, profile_id=profile_id)
    return success("Model profile archived", {"id": result.id, "isActive": result.is_active})


# --- Index profile routes ---------------------------------------------------


@index_profile_router.post("", status_code=status.HTTP_201_CREATED)
async def create_index_profile(
    payload: CreateIndexProfileRequest,
    svc: IndexProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await svc.create(
        tenant=tenant,
        name=payload.name,
        embedding_profile_id=payload.embedding_profile_id,
        sparse_profile_id=payload.sparse_profile_id,
        reranker_profile_id=payload.reranker_profile_id,
        collection=payload.collection,
        dimensions=payload.dimensions,
        distance_metric=payload.distance_metric,
        chunking_strategy=payload.chunking_strategy,
        chunk_size_tokens=payload.chunk_size_tokens,
        chunk_overlap_tokens=payload.chunk_overlap_tokens,
        parent_chunk_size=payload.parent_chunk_size,
    )
    return success(
        "Index profile created",
        {
            "id": result.id,
            "name": result.name,
            "collection": result.collection,
            "dimensions": result.dimensions,
            "distanceMetric": result.distance_metric,
            "chunkingStrategy": result.chunking_strategy,
            "chunkSizeTokens": result.chunk_size_tokens,
            "isActive": result.is_active,
            "createdAt": result.created_at,
        },
    )


@index_profile_router.get("")
async def list_index_profiles(
    svc: IndexProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    results = await svc.list_all(tenant=tenant)
    return success(
        "Index profiles loaded",
        [
            {
                "id": r.id,
                "name": r.name,
                "collection": r.collection,
                "dimensions": r.dimensions,
                "distanceMetric": r.distance_metric,
                "chunkingStrategy": r.chunking_strategy,
                "chunkSizeTokens": r.chunk_size_tokens,
                "embeddingProfileId": r.embedding_profile_id,
                "isActive": r.is_active,
                "createdAt": r.created_at,
            }
            for r in results
        ],
    )


@index_profile_router.post("/{profile_id}/activate")
async def activate_index_profile(
    profile_id: str,
    svc: IndexProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await svc.set_active(tenant=tenant, profile_id=profile_id)
    return success("Index profile activated", {"id": result.id, "isActive": result.is_active})


@index_profile_router.get("/{profile_id}/retrieval", response_model=RetrievalConfigResponse)
async def get_retrieval_config(
    profile_id: str,
    service: RetrievalConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await service.get(tenant=tenant, index_profile_id=profile_id)
    return {
        "index_profile_id": result.index_profile_id,
        "dense_weight": result.dense_weight,
        "sparse_weight": result.sparse_weight,
        "fusion_k": result.fusion_k,
        "dense_candidates": result.dense_candidates,
        "sparse_candidates": result.sparse_candidates,
        "fused_candidates": result.fused_candidates,
        "enabled": result.enabled,
    }


@index_profile_router.put("/{profile_id}/retrieval", response_model=RetrievalConfigResponse)
async def upsert_retrieval_config(
    profile_id: str,
    payload: RetrievalConfigRequest,
    service: RetrievalConfigServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    if tenant.role is not UserRole.ADMIN:
        from app.domain.errors import DomainError

        raise DomainError.forbidden("Administrator access required")
    result = await service.upsert(tenant=tenant, index_profile_id=profile_id, **payload.model_dump())
    return {
        "index_profile_id": result.index_profile_id,
        "dense_weight": result.dense_weight,
        "sparse_weight": result.sparse_weight,
        "fusion_k": result.fusion_k,
        "dense_candidates": result.dense_candidates,
        "sparse_candidates": result.sparse_candidates,
        "fused_candidates": result.fused_candidates,
        "enabled": result.enabled,
    }


@index_profile_router.delete("/{profile_id}/retrieval", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retrieval_config(
    profile_id: str,
    service: RetrievalConfigServiceDependency,
    tenant: TenantContextDependency,
) -> None:
    if tenant.role is not UserRole.ADMIN:
        from app.domain.errors import DomainError

        raise DomainError.forbidden("Administrator access required")
    await service.delete(tenant=tenant, index_profile_id=profile_id)


# --- Provider credential routes ---------------------------------------------


@provider_credential_router.post("", status_code=status.HTTP_200_OK)
async def set_provider_credential(
    payload: SetProviderCredentialRequest,
    svc: ProviderCredentialServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Set or update a provider credential. Value is never returned."""
    result = await svc.set_credential(
        tenant=tenant,
        provider=payload.provider,
        key_name=payload.key_name,
        value=payload.value,
    )
    return success(
        "Credential configured",
        {
            "provider": result.provider,
            "keyName": result.key_name,
            "isConfigured": result.is_configured,
            "updatedAt": result.updated_at,
        },
    )


@provider_credential_router.get("")
async def list_provider_credentials(
    svc: ProviderCredentialServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """List credential status for all supported providers. Values are never returned."""
    results = await svc.list_status(tenant=tenant)
    return success(
        "Provider credentials loaded",
        [
            {
                "provider": r.provider,
                "keyName": r.key_name,
                "isConfigured": r.is_configured,
                "updatedAt": r.updated_at,
            }
            for r in results
        ],
    )


@provider_credential_router.delete("/{provider}/{key_name}", status_code=status.HTTP_200_OK)
async def revoke_provider_credential(
    provider: str,
    key_name: str,
    svc: ProviderCredentialServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Revoke a provider credential."""
    result = await svc.revoke(tenant=tenant, provider=provider, key_name=key_name)
    return success(
        "Credential revoked",
        {
            "provider": result.provider,
            "keyName": result.key_name,
            "isConfigured": result.is_configured,
        },
    )


# --- Memory config routes ----------------------------------------------------

memory_config_router = APIRouter(prefix="/rag/knowledge-bases", tags=["Memory Config"])
memory_router = APIRouter(prefix="/rag/memory", tags=["User Memory"])


@memory_config_router.post("/{knowledge_base_id}/memory-config", status_code=status.HTTP_200_OK)
async def upsert_memory_config(
    knowledge_base_id: str,
    payload: CreateMemoryConfigRequest,
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
) -> dict[str, object]:
    result = await svc.upsert(
        tenant=tenant,
        knowledge_base_id=knowledge_base_id,
        enabled=payload.enabled,
        summarization_model_profile_id=payload.summarization_model_profile_id,
        embedding_profile_id=payload.embedding_profile_id,
        retention_days=payload.retention_days,
        retrieval_top_k=payload.retrieval_top_k,
        min_turns_to_summarize=payload.min_turns_to_summarize,
        system_prompt=payload.system_prompt,
    )
    return success(
        "Memory config saved",
        {
            "id": result.id,
            "knowledgeBaseId": result.knowledge_base_id,
            "enabled": result.enabled,
            "summarizationModelProfileId": result.summarization_model_profile_id,
            "embeddingProfileId": result.embedding_profile_id,
            "retentionDays": result.retention_days,
            "retrievalTopK": result.retrieval_top_k,
            "minTurnsToSummarize": result.min_turns_to_summarize,
            "systemPrompt": result.system_prompt,
            "createdAt": result.created_at.isoformat(),
            "updatedAt": result.updated_at.isoformat(),
        },
    )


@memory_config_router.get("/{knowledge_base_id}/memory-config")
async def get_memory_config(
    knowledge_base_id: str,
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
) -> dict[str, object]:
    result = await svc.get(tenant=tenant, knowledge_base_id=knowledge_base_id)
    return success(
        "Memory config loaded",
        {
            "id": result.id,
            "knowledgeBaseId": result.knowledge_base_id,
            "enabled": result.enabled,
            "summarizationModelProfileId": result.summarization_model_profile_id,
            "embeddingProfileId": result.embedding_profile_id,
            "retentionDays": result.retention_days,
            "retrievalTopK": result.retrieval_top_k,
            "minTurnsToSummarize": result.min_turns_to_summarize,
            "systemPrompt": result.system_prompt,
            "createdAt": result.created_at.isoformat(),
            "updatedAt": result.updated_at.isoformat(),
        },
    )


@memory_config_router.delete("/{knowledge_base_id}/memory-config", status_code=status.HTTP_200_OK)
async def delete_memory_config(
    knowledge_base_id: str,
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
) -> dict[str, object]:
    await svc.delete(tenant=tenant, knowledge_base_id=knowledge_base_id)
    return success("Memory config deleted")


@memory_config_router.get("/{knowledge_base_id}/memory-config/defaults")
async def get_memory_config_defaults(
    knowledge_base_id: str,
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
) -> dict[str, object]:
    return success("Memory config defaults loaded", svc.get_defaults())


# --- User memory management routes -------------------------------------------


@memory_router.get("")
async def list_memory_chunks(
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
    knowledge_base_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    from app.infrastructure.rag_catalog import SqlAlchemyMemoryChunkRepository

    # svc._session is available since MemoryConfigService holds session
    chunk_repo = SqlAlchemyMemoryChunkRepository(svc._session)
    if knowledge_base_id:
        chunks = await chunk_repo.find_by_user_kb(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id=tenant.user_id,
            page=page,
            page_size=page_size,
        )
        total = await chunk_repo.count_by_user_kb(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id=tenant.user_id,
        )
    else:
        chunks = []
        total = 0
    return success(
        "Memory chunks loaded",
        {
            "items": [
                {
                    "id": c.id,
                    "knowledgeBaseId": c.knowledge_base_id,
                    "userId": c.user_id,
                    "conversationId": c.conversation_id,
                    "summary": c.summary,
                    "turnCount": c.turn_count,
                    "expiresAt": c.expires_at.isoformat(),
                    "createdAt": c.created_at.isoformat(),
                }
                for c in chunks
            ],
            "total": total,
            "page": page,
            "pageSize": page_size,
        },
    )


@memory_router.delete("", status_code=status.HTTP_200_OK)
async def clear_memory(
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
    knowledge_base_id: str | None = None,
) -> dict[str, object]:
    from sqlalchemy import select

    from app.application.memory_summarizer import MemorySummarizer
    from app.infrastructure.rag_catalog import MemoryChunkRecord, SqlAlchemyMemoryChunkRepository

    chunk_repo = SqlAlchemyMemoryChunkRepository(svc._session)
    if knowledge_base_id:
        # Collect point_ids first
        result = await svc._session.execute(
            select(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant.tenant_id,
                MemoryChunkRecord.knowledge_base_id == knowledge_base_id,
                MemoryChunkRecord.user_id == tenant.user_id,
            )
        )
        chunks = result.scalars().all()
        point_ids = [c.qdrant_point_id for c in chunks]
        if point_ids:
            summarizer = MemorySummarizer(svc._settings)
            try:
                await summarizer.delete_qdrant_points_by_ids(point_ids=point_ids)
            except Exception:
                pass
        deleted = await chunk_repo.delete_by_user_kb(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id=tenant.user_id,
        )
    else:
        deleted = 0
    return success("Memory cleared", {"deleted": deleted})


@memory_router.delete("/{chunk_id}", status_code=status.HTTP_200_OK)
async def delete_memory_chunk(
    chunk_id: str,
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
) -> dict[str, object]:
    from app.application.memory_summarizer import MemorySummarizer
    from app.infrastructure.rag_catalog import SqlAlchemyMemoryChunkRepository

    chunk_repo = SqlAlchemyMemoryChunkRepository(svc._session)
    chunk = await chunk_repo.find_by_id(tenant_id=tenant.tenant_id, chunk_id=chunk_id)
    if chunk is None or chunk.user_id != tenant.user_id:
        from app.domain.errors import DomainError

        raise DomainError.not_found("Memory chunk not found")

    summarizer = MemorySummarizer(svc._settings)
    try:
        await summarizer.delete_qdrant_points_by_ids(point_ids=[chunk.qdrant_point_id])
    except Exception:
        pass

    await chunk_repo.delete(
        tenant_id=tenant.tenant_id,
        chunk_id=chunk_id,
        user_id=tenant.user_id,
    )
    return success("Memory chunk deleted")
