import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.rag_query_service import RagQueryService
from app.core.security import decode_refresh_token
from app.core.settings import Settings, get_settings
from app.infrastructure.database import get_session
from app.interfaces.http.dependencies import (
    AuthContextDependency,
    AuthServiceDependency,
    DecompositionConfigServiceDependency,
    IndexProfileServiceDependency,
    IngestionServiceDependency,
    KnowledgeBaseServiceDependency,
    MemoryConfigServiceDependency,
    ModelProfileServiceDependency,
    ProviderCredentialServiceDependency,
    RagQueryServiceDependency,
    RagTraceServiceDependency,
    SessionDependency,
    TenantContextDependency,
)
from app.interfaces.http.schemas import (
    CompleteIntakeRequest,
    CreateDecompositionConfigRequest,
    CreateIndexProfileRequest,
    CreateIntakeRequest,
    CreateKnowledgeBaseRequest,
    CreateMemoryConfigRequest,
    CreateModelProfileRequest,
    LoginRequest,
    RagAnswerFeedbackRequest,
    RagQueryRequest,
    RegisterRequest,
    SetProviderCredentialRequest,
)

system_router = APIRouter(tags=["System"])
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
rag_router = APIRouter(prefix="/rag", tags=["RAG Ingestion"])
rag_query_router = APIRouter(prefix="/rag/query", tags=["RAG Query"])
kb_router = APIRouter(prefix="/rag/knowledge-bases", tags=["Knowledge Bases"])
model_profile_router = APIRouter(prefix="/rag/model-profiles", tags=["Model Profiles"])
index_profile_router = APIRouter(prefix="/rag/index-profiles", tags=["Index Profiles"])
provider_credential_router = APIRouter(prefix="/rag/provider-credentials", tags=["Provider Credentials"])


def success(message: str, data: object | None = None, meta: object | None = None) -> dict[str, object]:
    response: dict[str, object] = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    if meta is not None:
        response["meta"] = meta
    return response


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
            memory_enabled=memory_enabled,
            session=session,
        )
    except Exception:
        yield _sse_event("response.failed", {"code": "QUERY_FAILED"})
        return

    trace_id = result["traceId"]
    yield _sse_event("response.started", {"traceId": trace_id})
    yield _sse_event("response.route", {"route": result["route"]})

    # tool_call and tool_result events — emitted only when route is "tool"
    for tool_event in result.get("toolCalls", []):
        yield _sse_event("response.tool_call", {
            "toolSlug": tool_event.get("toolSlug"),
            "inputHash": tool_event.get("inputHash"),
            "traceId": trace_id,
        })
        yield _sse_event("response.tool_result", {
            "toolSlug": tool_event.get("toolSlug"),
            "evidenceCount": tool_event.get("evidenceCount", 0),
            "latencyMs": tool_event.get("latencyMs"),
            "status": tool_event.get("status"),
        })

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
    return success("Knowledge base created", {
        "id": result.id,
        "tenantId": result.tenant_id,
        "slug": result.slug,
        "name": result.name,
        "status": result.status,
        "createdAt": result.created_at,
        "updatedAt": result.updated_at,
    })


@kb_router.get("")
async def list_knowledge_bases(
    kb_service: KnowledgeBaseServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """List all active knowledge bases for the authenticated tenant."""
    results = await kb_service.list_all(tenant=tenant)
    return success("Knowledge bases loaded", [
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
    ])


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
    return success("Knowledge base archived", {
        "id": result.id,
        "status": result.status,
    })


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
    return success("Model profile created", {
        "id": result.id, "name": result.name, "profileKind": result.profile_kind,
        "provider": result.provider, "model": result.model, "modality": result.modality,
        "dimensions": result.dimensions, "version": result.version,
        "isActive": result.is_active, "createdAt": result.created_at,
    })


@model_profile_router.get("")
async def list_model_profiles(
    svc: ModelProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    results = await svc.list_all(tenant=tenant)
    return success("Model profiles loaded", [
        {"id": r.id, "name": r.name, "profileKind": r.profile_kind,
         "provider": r.provider, "model": r.model, "modality": r.modality,
         "dimensions": r.dimensions, "version": r.version,
         "isActive": r.is_active, "createdAt": r.created_at}
        for r in results
    ])


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
    return success("Index profile created", {
        "id": result.id, "name": result.name, "collection": result.collection,
        "dimensions": result.dimensions, "distanceMetric": result.distance_metric,
        "chunkingStrategy": result.chunking_strategy, "chunkSizeTokens": result.chunk_size_tokens,
        "isActive": result.is_active, "createdAt": result.created_at,
    })


@index_profile_router.get("")
async def list_index_profiles(
    svc: IndexProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    results = await svc.list_all(tenant=tenant)
    return success("Index profiles loaded", [
        {"id": r.id, "name": r.name, "collection": r.collection,
         "dimensions": r.dimensions, "distanceMetric": r.distance_metric,
         "chunkingStrategy": r.chunking_strategy, "chunkSizeTokens": r.chunk_size_tokens,
         "embeddingProfileId": r.embedding_profile_id, "isActive": r.is_active,
         "createdAt": r.created_at}
        for r in results
    ])


@index_profile_router.post("/{profile_id}/activate")
async def activate_index_profile(
    profile_id: str,
    svc: IndexProfileServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    result = await svc.set_active(tenant=tenant, profile_id=profile_id)
    return success("Index profile activated", {"id": result.id, "isActive": result.is_active})


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
    return success("Credential configured", {
        "provider": result.provider,
        "keyName": result.key_name,
        "isConfigured": result.is_configured,
        "updatedAt": result.updated_at,
    })


@provider_credential_router.get("")
async def list_provider_credentials(
    svc: ProviderCredentialServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """List credential status for all supported providers. Values are never returned."""
    results = await svc.list_status(tenant=tenant)
    return success("Provider credentials loaded", [
        {
            "provider": r.provider,
            "keyName": r.key_name,
            "isConfigured": r.is_configured,
            "updatedAt": r.updated_at,
        }
        for r in results
    ])


@provider_credential_router.delete("/{provider}/{key_name}", status_code=status.HTTP_200_OK)
async def revoke_provider_credential(
    provider: str,
    key_name: str,
    svc: ProviderCredentialServiceDependency,
    tenant: TenantContextDependency,
) -> dict[str, object]:
    """Revoke a provider credential."""
    result = await svc.revoke(tenant=tenant, provider=provider, key_name=key_name)
    return success("Credential revoked", {
        "provider": result.provider,
        "keyName": result.key_name,
        "isConfigured": result.is_configured,
    })


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
    return success("Memory config saved", {
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
    })


@memory_config_router.get("/{knowledge_base_id}/memory-config")
async def get_memory_config(
    knowledge_base_id: str,
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
) -> dict[str, object]:
    result = await svc.get(tenant=tenant, knowledge_base_id=knowledge_base_id)
    return success("Memory config loaded", {
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
    })


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
    return success("Memory chunks loaded", {
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
    })


@memory_router.delete("", status_code=status.HTTP_200_OK)
async def clear_memory(
    tenant: TenantContextDependency,
    svc: MemoryConfigServiceDependency,
    knowledge_base_id: str | None = None,
) -> dict[str, object]:
    from app.application.memory_summarizer import MemorySummarizer
    from app.infrastructure.rag_catalog import MemoryChunkRecord, SqlAlchemyMemoryChunkRepository
    from sqlalchemy import select

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
