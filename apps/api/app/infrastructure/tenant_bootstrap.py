"""Deployment tenant bootstrap, verification, and membership backfill.

This module runs at application startup to:

1. Verify ``DEPLOYMENT_TENANT_ID`` is present and valid (fails fast otherwise).
2. Bootstrap (create) the sole deployment tenant record if it does not exist yet.
3. Verify the persisted tenant matches the configured ID (fail on mismatch —
   in-place tenant ID change is unsupported).
4. Backfill active memberships for all existing users who do not yet have one.
5. Expose operator diagnostics including the active tenant mode.

None of these steps accept a tenant value from a client request, header, path,
query parameter, body, or JWT claim. The tenant identity is always derived from
deployment configuration.
"""

from dataclasses import dataclass

from app.core.settings import TENANT_MODE_SINGLE_DEPLOYMENT, Settings
from app.domain.errors import DomainError
from app.domain.models import TenantMembershipStatus
from app.infrastructure.database import SqlAlchemyTenantRepository, create_session_factory


@dataclass(frozen=True)
class TenantBootstrapResult:
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    mode: str
    memberships_backfilled: int


async def verify_and_bootstrap_tenant(settings: Settings) -> TenantBootstrapResult:
    """Verify the deployment tenant at startup.

    Raises ``DomainError`` if the configuration is missing, the persisted
    tenant does not match, or the tenant mode is unsupported.
    """
    if settings.deployment_tenant_id is None:
        raise DomainError.tenant_not_configured()

    session_factory = create_session_factory(settings)
    async with session_factory() as session:
        repository = SqlAlchemyTenantRepository(session)
        tenant = await repository.find_tenant_by_id(settings.deployment_tenant_id)

        if tenant is None:
            # Bootstrap: create the sole deployment tenant.
            # If another active tenant already exists (from a prior config),
            # reject because in-place tenant ID change is unsupported.
            existing = await repository.find_active_tenant()
            if existing is not None:
                raise DomainError.tenant_mismatch(
                    configured_id=settings.deployment_tenant_id,
                    persisted_id=existing.id,
                )
            tenant = await repository.create_tenant(
                tenant_id=settings.deployment_tenant_id,
                slug=f"deployment-{settings.deployment_tenant_id[:8]}",
                name="Deployment Tenant",
            )
        elif tenant.id != settings.deployment_tenant_id:
            raise DomainError.tenant_mismatch(
                configured_id=settings.deployment_tenant_id,
                persisted_id=tenant.id,
            )

        # Backfill active memberships for existing users without one.
        backfilled = await repository.backfill_memberships(
            tenant_id=tenant.id,
            status=TenantMembershipStatus.ACTIVE,
        )

        # Every tenant must have an active default Project so new Knowledge
        # Bases are never left without an owning workspace.
        from app.infrastructure.rag_projects import SqlAlchemyProjectRepository

        project_repository = SqlAlchemyProjectRepository(session)
        if await project_repository.find_default(tenant_id=tenant.id) is None:
            await project_repository.create(
                tenant_id=tenant.id,
                slug="default",
                name="Default Project",
                is_default=True,
            )

        # New deployments created after the policy migration receive the same
        # explicit, versioned defaults as existing tenants. Missing policy is
        # never silently replaced in the query path.
        from app.domain.models import PolicyScope
        from app.domain.rag.answer_policy import AnswerBehaviorProfile, GuardrailProfile
        from app.infrastructure.answer_policy import (
            SqlAlchemyAnswerBehaviorProfileRepository,
            SqlAlchemyGuardrailProfileRepository,
        )

        answer_profiles = SqlAlchemyAnswerBehaviorProfileRepository(session)
        if await answer_profiles.find_active_deployment(tenant_id=tenant.id) is None:
            await answer_profiles.create(
                tenant_id=tenant.id,
                knowledge_base_id=None,
                profile=AnswerBehaviorProfile(version="migrated-default-v1", scope=PolicyScope.DEPLOYMENT),
                created_by=None,
            )
        guardrail_profiles = SqlAlchemyGuardrailProfileRepository(session)
        if await guardrail_profiles.find_active_deployment(tenant_id=tenant.id) is None:
            await guardrail_profiles.create(
                tenant_id=tenant.id,
                knowledge_base_id=None,
                profile=GuardrailProfile.platform_baseline(),
                created_by=None,
            )

    return TenantBootstrapResult(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        mode=settings.tenant_mode,
        memberships_backfilled=backfilled,
    )


def tenant_diagnostics(settings: Settings, bootstrap: TenantBootstrapResult | None) -> dict[str, object]:
    """Return operator diagnostics for the deployment tenant."""
    diagnostics: dict[str, object] = {
        "tenantMode": settings.tenant_mode,
        "deploymentTenantId": settings.deployment_tenant_id,
    }
    if bootstrap is not None:
        diagnostics["tenantId"] = bootstrap.tenant_id
        diagnostics["tenantSlug"] = bootstrap.tenant_slug
        diagnostics["tenantName"] = bootstrap.tenant_name
        diagnostics["membershipsBackfilled"] = bootstrap.memberships_backfilled
    diagnostics["supportedModes"] = [TENANT_MODE_SINGLE_DEPLOYMENT]
    return diagnostics
