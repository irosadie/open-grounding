"""Promotion of advanced index profiles only after labeled evaluation evidence."""

from app.application.rag_evaluation import RagEvaluationService
from app.domain.errors import DomainError
from app.domain.rag.repositories import IndexProfileRepository
from app.domain.tenant_context import TenantContext


class RagProfilePromotionService:
    def __init__(self, evaluations: RagEvaluationService, profiles: IndexProfileRepository) -> None:
        self._evaluations = evaluations
        self._profiles = profiles

    async def promote(self, *, tenant: TenantContext, profile_id: str) -> dict[str, object]:
        await self._evaluations.require_passing_evidence(tenant=tenant, profile_id=profile_id)
        profile = await self._profiles.activate(tenant_id=tenant.tenant_id, profile_id=profile_id)
        if profile is None:
            raise DomainError("INDEX_PROFILE_NOT_FOUND", "Index profile not found", 404)
        return {"profileId": profile.id, "isActive": profile.is_active}
