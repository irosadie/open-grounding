import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse

from app.application.rag_query_service import RagQueryService
from app.core.security import decode_refresh_token
from app.core.settings import Settings, get_settings
from app.interfaces.http.dependencies import (
    AuthContextDependency,
    AuthServiceDependency,
    IndexProfileServiceDependency,
    IngestionServiceDependency,
    KnowledgeBaseServiceDependency,
    ModelProfileServiceDependency,
    ProviderCredentialServiceDependency,
    RagQueryServiceDependency,
    RagTraceServiceDependency,
    TenantContextDependency,
)
from app.interfaces.http.schemas import (
    CompleteIntakeRequest,
    CreateIndexProfileRequest,
    CreateIntakeRequest,
    CreateKnowledgeBaseRequest,
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
) -> dict[str, object] | StreamingResponse:
    if payload.stream:
        return StreamingResponse(
            _stream_query(
                service,
                tenant=tenant,
                message=payload.message,
                knowledge_base_ids=tuple(payload.knowledge_base_ids),
                conversation_id=payload.conversation_id,
            ),
            media_type="text/event-stream",
        )
    result = await service.query(
        tenant=tenant,
        message=payload.message,
        knowledge_base_ids=tuple(payload.knowledge_base_ids),
        conversation_id=payload.conversation_id,
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
) -> AsyncIterator[str]:
    try:
        result = await service.query(
            tenant=tenant,
            message=message,
            knowledge_base_ids=knowledge_base_ids,
            conversation_id=conversation_id,
        )
    except Exception:
        yield _sse_event("response.failed", {"code": "QUERY_FAILED"})
        return

    trace_id = result["traceId"]
    yield _sse_event("response.started", {"traceId": trace_id})
    yield _sse_event("response.route", {"route": result["route"]})
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
