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
    IngestionServiceDependency,
    RagQueryServiceDependency,
    RagTraceServiceDependency,
    TenantContextDependency,
)
from app.interfaces.http.schemas import (
    CompleteIntakeRequest,
    CreateIntakeRequest,
    LoginRequest,
    RagAnswerFeedbackRequest,
    RagQueryRequest,
    RegisterRequest,
)

system_router = APIRouter(tags=["System"])
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
rag_router = APIRouter(prefix="/rag", tags=["RAG Ingestion"])
rag_query_router = APIRouter(prefix="/rag/query", tags=["RAG Query"])


def success(message: str, data: object | None = None, meta: object | None = None) -> dict[str, object]:
    response: dict[str, object] = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    if meta is not None:
        response["meta"] = meta
    return response


@system_router.get("/")
async def get_app_info() -> dict[str, object]:
    return success("Application info loaded", {"name": "vibecoding-starter-api", "message": "FastAPI clean architecture API is ready"})


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
            "service": "vibecoding-starter-api",
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
