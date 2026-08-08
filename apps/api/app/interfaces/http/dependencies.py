from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthService
from app.application.confidence_service import ConfidenceService
from app.application.decomposition_config_service import DecompositionConfigService
from app.application.ingestion_config_service import IngestionConfigService
from app.application.ingestion_intake_service import IngestionIntakeService
from app.application.knowledge_base_service import KnowledgeBaseService
from app.application.mcp_runtime_service import McpRuntimeService
from app.application.memory_config_service import MemoryConfigService
from app.application.planner_config_service import PlannerConfigService
from app.application.profile_service import IndexProfileService, ModelProfileService
from app.application.provider_credential_service import ProviderCredentialService
from app.application.rag_generation import RagGenerationService
from app.application.rag_hybrid_retrieval import RagHybridRetrievalService
from app.application.rag_query_admission import RagQueryAdmission
from app.application.rag_query_service import RagQueryService
from app.application.rag_trace_service import RagTraceService
from app.application.retrieval_config_service import RetrievalConfigService
from app.core.security import decode_access_token
from app.core.settings import Settings, get_settings
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext
from app.infrastructure.database import SqlAlchemyAuthRepository, SqlAlchemyTenantRepository, get_session
from app.infrastructure.embedding_adapter import ProfileSparseEncoderAdapter, ProviderEmbeddingAdapter
from app.infrastructure.generation_adapter import LLMGenerationAdapter
from app.infrastructure.mcp.connection_manager import McpConnectionManager
from app.infrastructure.qdrant import QdrantVectorStoreAdapter
from app.infrastructure.rag_answer_trace import SqlAlchemyAnswerFeedbackRepository, SqlAlchemyAnswerRunRepository, SqlAlchemyAnswerTraceDetailRepository
from app.infrastructure.rag_catalog import (
    SqlAlchemyDecompositionConfigRepository,
    SqlAlchemyIndexGenerationRepository,
    SqlAlchemyIndexProfileRepository,
    SqlAlchemyIngestionConfigRepository,
    SqlAlchemyKnowledgeBaseRepository,
    SqlAlchemyMcpInvocationRepository,
    SqlAlchemyMcpServerRepository,
    SqlAlchemyMcpToolRepository,
    SqlAlchemyPlannerConfigRepository,
    SqlAlchemyRetrievalConfigRepository,
    SqlCalibrationFixtureRepository,
    SqlCalibrationModelRepository,
    SqlConfidenceConfigRepository,
)
from app.infrastructure.rag_conversations import SqlAlchemyConversationHistoryRepository


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(SqlAlchemyAuthRepository(session), settings)


async def get_auth_context(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise DomainError.unauthorized()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise DomainError.unauthorized()
    payload = decode_access_token(token, settings)
    if payload.get("status") == "SUSPENDED":
        raise DomainError.forbidden("Account is suspended")
    if payload.get("type") not in {"admin", "user"}:
        raise DomainError.invalid_token("Invalid token payload")
    return {**payload, "accessToken": token}


def get_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestionIntakeService:
    return IngestionIntakeService(session, settings)


def get_rag_query_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RagQueryService:
    return RagQueryService(
        settings,
        SqlAlchemyAnswerRunRepository(session),
        get_rag_query_admission(),
        SqlAlchemyKnowledgeBaseRepository(session),
        SqlAlchemyConversationHistoryRepository(session),
        SqlAlchemyIndexGenerationRepository(session),
        SqlAlchemyAnswerTraceDetailRepository(session),
        SqlAlchemyDecompositionConfigRepository(session),
        SqlAlchemyIndexProfileRepository(session),
        _retrieval_service(settings, session),
        _generation_service(settings),
        planner_configs=SqlAlchemyPlannerConfigRepository(session),
        mcp_runtime=get_mcp_runtime_service(session, settings, get_mcp_connection_manager()),
    )


def _retrieval_service(settings: Settings, session: AsyncSession) -> RagHybridRetrievalService:
    import httpx

    client = httpx.AsyncClient(timeout=30.0)
    qdrant = QdrantVectorStoreAdapter(settings, client)
    return RagHybridRetrievalService(
        settings,
        ProviderEmbeddingAdapter(settings),
        ProfileSparseEncoderAdapter(settings),
        qdrant,
        SqlAlchemyRetrievalConfigRepository(session),
    )


def _generation_service(settings: Settings) -> RagGenerationService:
    return RagGenerationService(settings, LLMGenerationAdapter(settings))


def get_rag_trace_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RagTraceService:
    return RagTraceService(settings, SqlAlchemyAnswerRunRepository(session), SqlAlchemyAnswerFeedbackRepository(session))


@lru_cache
def get_rag_query_admission() -> RagQueryAdmission:
    return RagQueryAdmission(get_settings())


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
AuthContextDependency = Annotated[dict[str, str], Depends(get_auth_context)]
IngestionServiceDependency = Annotated[IngestionIntakeService, Depends(get_ingestion_service)]
RagQueryServiceDependency = Annotated[RagQueryService, Depends(get_rag_query_service)]
RagTraceServiceDependency = Annotated[RagTraceService, Depends(get_rag_trace_service)]


async def get_tenant_context(
    request: Request,
    auth_context: AuthContextDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TenantContext:
    """Resolve the immutable tenant context from deployment configuration and
    authenticated active membership.

    The deployment tenant ID is read from application state (set during startup
    verification). Client-supplied tenant values in headers, path, query, body,
    or JWT claims are never used.
    """
    if settings.deployment_tenant_id is None:
        raise DomainError.tenant_not_configured()

    bootstrap = getattr(request.app.state, "tenant_bootstrap_result", None)
    if bootstrap is None:
        raise DomainError.tenant_not_configured()

    tenant_repo = SqlAlchemyTenantRepository(session)
    membership = await tenant_repo.find_active_membership(
        tenant_id=bootstrap.tenant_id,
        user_id=auth_context["id"],
    )
    if membership is None:
        raise DomainError.tenant_membership_inactive()

    return TenantContext(
        tenant_id=bootstrap.tenant_id,
        membership_id=membership.id,
        user_id=auth_context["id"],
        role=UserRole.ADMIN if auth_context["type"] == "admin" else UserRole.USER,
    )


TenantContextDependency = Annotated[TenantContext, Depends(get_tenant_context)]


def get_knowledge_base_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeBaseService:
    return KnowledgeBaseService(session)


KnowledgeBaseServiceDependency = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]


def get_ingestion_config_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestionConfigService:
    return IngestionConfigService(session)


IngestionConfigServiceDependency = Annotated[IngestionConfigService, Depends(get_ingestion_config_service)]


def get_model_profile_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ModelProfileService:
    return ModelProfileService(session)


def get_index_profile_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexProfileService:
    return IndexProfileService(session)


ModelProfileServiceDependency = Annotated[ModelProfileService, Depends(get_model_profile_service)]
IndexProfileServiceDependency = Annotated[IndexProfileService, Depends(get_index_profile_service)]


def get_provider_credential_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProviderCredentialService:
    return ProviderCredentialService(session, settings)


ProviderCredentialServiceDependency = Annotated[ProviderCredentialService, Depends(get_provider_credential_service)]


def get_decomposition_config_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DecompositionConfigService:
    return DecompositionConfigService(session, settings)


DecompositionConfigServiceDependency = Annotated[DecompositionConfigService, Depends(get_decomposition_config_service)]


def get_planner_config_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlannerConfigService:
    return PlannerConfigService(session, settings)


PlannerConfigServiceDependency = Annotated[PlannerConfigService, Depends(get_planner_config_service)]


def get_memory_config_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryConfigService:
    return MemoryConfigService(session, settings)


MemoryConfigServiceDependency = Annotated[MemoryConfigService, Depends(get_memory_config_service)]


def get_retrieval_config_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrievalConfigService:
    return RetrievalConfigService(session, settings)


RetrievalConfigServiceDependency = Annotated[RetrievalConfigService, Depends(get_retrieval_config_service)]


def get_confidence_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfidenceService:
    return ConfidenceService(
        SqlConfidenceConfigRepository(session),
        SqlCalibrationFixtureRepository(session),
        SqlCalibrationModelRepository(session),
        SqlAlchemyAnswerRunRepository(session),
    )


ConfidenceServiceDependency = Annotated[ConfidenceService, Depends(get_confidence_service)]


@lru_cache
def get_mcp_connection_manager() -> McpConnectionManager:
    return McpConnectionManager()


def get_mcp_runtime_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    connections: Annotated[McpConnectionManager, Depends(get_mcp_connection_manager)],
) -> McpRuntimeService:
    return McpRuntimeService(
        settings,
        SqlAlchemyMcpServerRepository(session),
        SqlAlchemyMcpToolRepository(session),
        SqlAlchemyMcpInvocationRepository(session),
        ProviderCredentialService(session, settings),
        connections,
    )


McpRuntimeServiceDependency = Annotated[McpRuntimeService, Depends(get_mcp_runtime_service)]

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
