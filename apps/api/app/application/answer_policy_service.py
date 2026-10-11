"""Application service for versioned answer behavior and guardrail settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import (
    AnswerSourcePolicy,
    GreetingPolicy,
    NoEvidenceAction,
    PolicyScope,
    ResponseStyle,
    UserRole,
)
from app.domain.rag.answer_policy import (
    DEFAULT_DEPLOYMENT_MAX_OUTPUT_TOKENS,
    AnswerBehaviorProfile,
    EffectiveAnswerPolicy,
    GuardrailProfile,
    PersistedAnswerBehavior,
    PersistedGuardrailProfile,
    resolve_effective_policy,
)
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_metrics import record_project_metric

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AnswerPolicyService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def resolve_effective(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str | None = None,
        knowledge_base_ids: tuple[str, ...] = (),
        project_id: str | None = None,
    ) -> EffectiveAnswerPolicy:
        from app.infrastructure.answer_policy import (
            SqlAlchemyAnswerBehaviorProfileRepository,
            SqlAlchemyGuardrailProfileRepository,
        )

        answer_repo = SqlAlchemyAnswerBehaviorProfileRepository(self._session)
        guardrail_repo = SqlAlchemyGuardrailProfileRepository(self._session)
        from app.infrastructure.rag_projects import SqlAlchemyProjectRepository

        selected_ids = tuple(
            dict.fromkeys(
                (*knowledge_base_ids, *((knowledge_base_id,) if knowledge_base_id is not None else ()))
            )
        )
        project = None
        if project_id is not None:
            project = await SqlAlchemyProjectRepository(self._session).find_by_id(
                tenant_id=tenant.tenant_id, project_id=project_id
            )
            if project is None or str(project.status) != "ACTIVE":
                record_project_metric(
                    tenant_id=tenant.tenant_id,
                    metric="resolution",
                    outcome="rejected",
                    project_id=project_id,
                    knowledge_base_count=len(selected_ids),
                    reason_code="PROJECT_NOT_FOUND_OR_INACTIVE",
                )
                raise DomainError.not_found("Project not found")
            if selected_ids:
                resolved = await SqlAlchemyProjectRepository(self._session).resolve_project_for_knowledge_bases(
                    tenant_id=tenant.tenant_id, knowledge_base_ids=selected_ids
                )
                if resolved is None or resolved.id != project.id:
                    record_project_metric(
                        tenant_id=tenant.tenant_id,
                        metric="resolution",
                        outcome="rejected",
                        project_id=project_id,
                        knowledge_base_count=len(selected_ids),
                        reason_code="PROJECT_SCOPE_CONFLICT",
                    )
                    raise DomainError("PROJECT_SCOPE_CONFLICT", "Selected knowledge bases do not belong to the Project", 422)
        elif selected_ids:
            project = await SqlAlchemyProjectRepository(self._session).resolve_project_for_knowledge_bases(
                tenant_id=tenant.tenant_id, knowledge_base_ids=selected_ids
            )
            if project is None:
                record_project_metric(
                    tenant_id=tenant.tenant_id,
                    metric="resolution",
                    outcome="rejected",
                    knowledge_base_count=len(selected_ids),
                    reason_code="PROJECT_SCOPE_CONFLICT",
                )
                raise DomainError("PROJECT_SCOPE_CONFLICT", "Selected knowledge bases do not resolve to one active Project", 422)
        deployment_answer = await answer_repo.find_active_deployment(tenant_id=tenant.tenant_id)
        deployment_guardrails = await guardrail_repo.find_active_deployment(tenant_id=tenant.tenant_id)
        if deployment_answer is None or deployment_guardrails is None:
            raise DomainError("POLICY_UNAVAILABLE", "Effective answer policy is unavailable", 503)
        project_answer = await answer_repo.find_active_for_project(tenant_id=tenant.tenant_id, project_id=project.id) if project else None
        project_guardrails = await guardrail_repo.find_active_for_project(tenant_id=tenant.tenant_id, project_id=project.id) if project else None
        legacy_kb_id = selected_ids[0] if len(selected_ids) == 1 else None
        knowledge_base_answer = (
            await answer_repo.find_active_for_knowledge_base(
                tenant_id=tenant.tenant_id, knowledge_base_id=legacy_kb_id
            )
            if legacy_kb_id and project_answer is None and self._settings.rag_project_legacy_fallback_enabled
            else None
        )
        knowledge_base_guardrails = (
            await guardrail_repo.find_active_for_knowledge_base(
                tenant_id=tenant.tenant_id, knowledge_base_id=legacy_kb_id
            )
            if legacy_kb_id and project_guardrails is None and self._settings.rag_project_legacy_fallback_enabled
            else None
        )
        if knowledge_base_answer is not None or knowledge_base_guardrails is not None:
            record_project_metric(
                tenant_id=tenant.tenant_id,
                metric="legacy_fallback",
                outcome="used",
                project_id=project.id if project else None,
                knowledge_base_count=len(selected_ids),
                reason_code="LEGACY_KB_POLICY_FALLBACK",
            )
        elif project is not None:
            record_project_metric(
                tenant_id=tenant.tenant_id,
                metric="resolution",
                outcome="success",
                project_id=project.id,
                knowledge_base_count=len(selected_ids),
                reason_code="PROJECT_RESOLVED",
            )
        effective = resolve_effective_policy(
            deployment=deployment_answer.profile,
            baseline_guardrails=deployment_guardrails.profile,
            project_override=project_answer.profile if project_answer else None,
            knowledge_base_override=knowledge_base_answer.profile if knowledge_base_answer else None,
            project_guardrails=project_guardrails.profile if project_guardrails else None,
            knowledge_base_guardrails=knowledge_base_guardrails.profile if knowledge_base_guardrails else None,
        )
        return effective

    async def get_effective(
        self, *, tenant: TenantContext, knowledge_base_id: str | None = None, project_id: str | None = None
    ) -> dict[str, object]:
        effective = await self.resolve_effective(tenant=tenant, knowledge_base_id=knowledge_base_id, project_id=project_id)
        return {
            "knowledgeBaseId": knowledge_base_id,
            "projectId": project_id,
            "answerBehaviorVersion": effective.answer_behavior_version,
            "guardrailVersion": effective.guardrail_version,
            "answerBehavior": _answer_behavior_to_dict(effective.answer_behavior),
            "guardrails": _guardrail_to_dict(effective.guardrails),
        }

    async def ensure_project(self, *, tenant: TenantContext, project_id: str) -> None:
        await self._require_project(tenant=tenant, project_id=project_id)

    async def record_decision(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str | None,
        project_id: str | None = None,
        policy: EffectiveAnswerPolicy,
        stage: str,
        decision: str,
        reason: str,
        trace_id: str | None,
    ) -> None:
        """Persist only redacted policy metadata, never query/tool content."""
        from app.infrastructure.answer_policy import SqlAlchemyPolicyAuditRepository

        await SqlAlchemyPolicyAuditRepository(self._session).record(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            knowledge_base_id=knowledge_base_id,
            project_id=project_id,
            policy_kind=f"GUARDRAIL_{stage}",
            policy_version=policy.guardrail_version,
            action=decision,
            changes={"stage": stage, "decision": decision, "reason": reason[:160]},
            trace_id=trace_id,
        )

    async def save_answer_behavior(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        version: str,
        persona: str,
        response_style: str,
        max_output_tokens: int,
        source_policy: str,
        greeting_policy: str,
        no_evidence_action: str,
        require_citations: bool,
        allow_mcp_sources: bool,
    ) -> dict[str, object]:
        self._require_admin(tenant)
        self._require_legacy_kb_writes_enabled()
        self._validate_output_budget(max_output_tokens)
        try:
            profile = AnswerBehaviorProfile(
                version=version,
                scope=PolicyScope.KNOWLEDGE_BASE,
                persona=persona,
                response_style=ResponseStyle(response_style),
                max_output_tokens=max_output_tokens,
                source_policy=AnswerSourcePolicy(source_policy),
                greeting_policy=GreetingPolicy(greeting_policy),
                no_evidence_action=NoEvidenceAction(no_evidence_action),
                require_citations=require_citations,
                allow_mcp_sources=allow_mcp_sources,
            )
        except ValueError as exc:
            raise DomainError.validation(str(exc)) from exc

        from app.infrastructure.answer_policy import (
            SqlAlchemyAnswerBehaviorProfileRepository,
            SqlAlchemyPolicyAuditRepository,
        )

        repo = SqlAlchemyAnswerBehaviorProfileRepository(self._session)
        existing = await repo.find_active_for_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if existing:
            await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)
        created = await repo.create(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            profile=profile,
            created_by=tenant.user_id,
        )
        await SqlAlchemyPolicyAuditRepository(self._session).record(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            knowledge_base_id=knowledge_base_id,
            policy_kind="ANSWER_BEHAVIOR",
            policy_version=profile.version,
            action="ACTIVATE",
            changes=_answer_behavior_to_dict(profile),
        )
        return _persisted_answer_to_dict(created)

    async def get_answer_behavior(self, *, tenant: TenantContext, knowledge_base_id: str) -> dict[str, object]:
        from app.infrastructure.answer_policy import SqlAlchemyAnswerBehaviorProfileRepository

        value = await SqlAlchemyAnswerBehaviorProfileRepository(self._session).find_active_for_knowledge_base(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )
        if value is None:
            raise DomainError.not_found("Answer behavior override not found")
        return _persisted_answer_to_dict(value)

    async def save_guardrails(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        version: str,
        input_rules: list[str],
        tool_rules: list[str],
        output_rules: list[str],
        max_tool_calls: int,
        max_tool_timeout_seconds: int,
        max_tool_payload_bytes: int,
        max_mcp_freshness_seconds: int,
        require_tool_confirmation: bool,
    ) -> dict[str, object]:
        self._require_admin(tenant)
        self._require_legacy_kb_writes_enabled()
        try:
            profile = GuardrailProfile(
                version=version,
                scope=PolicyScope.KNOWLEDGE_BASE,
                input_rules=tuple(input_rules),
                tool_rules=tuple(tool_rules),
                output_rules=tuple(output_rules),
                max_tool_calls=max_tool_calls,
                max_tool_timeout_seconds=max_tool_timeout_seconds,
                max_tool_payload_bytes=max_tool_payload_bytes,
                max_mcp_freshness_seconds=max_mcp_freshness_seconds,
                require_tool_confirmation=require_tool_confirmation,
            )
        except ValueError as exc:
            raise DomainError.validation(str(exc)) from exc

        from app.infrastructure.answer_policy import (
            SqlAlchemyGuardrailProfileRepository,
            SqlAlchemyPolicyAuditRepository,
        )

        repo = SqlAlchemyGuardrailProfileRepository(self._session)
        existing = await repo.find_active_for_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if existing:
            await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)
        created = await repo.create(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            profile=profile,
            created_by=tenant.user_id,
        )
        await SqlAlchemyPolicyAuditRepository(self._session).record(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            knowledge_base_id=knowledge_base_id,
            policy_kind="GUARDRAIL",
            policy_version=profile.version,
            action="ACTIVATE",
            changes=_guardrail_to_dict(profile),
        )
        return _persisted_guardrail_to_dict(created)

    async def get_guardrails(self, *, tenant: TenantContext, knowledge_base_id: str) -> dict[str, object]:
        from app.infrastructure.answer_policy import SqlAlchemyGuardrailProfileRepository

        value = await SqlAlchemyGuardrailProfileRepository(self._session).find_active_for_knowledge_base(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )
        if value is None:
            raise DomainError.not_found("Guardrail override not found")
        return _persisted_guardrail_to_dict(value)

    async def delete_answer_behavior(self, *, tenant: TenantContext, knowledge_base_id: str) -> bool:
        self._require_admin(tenant)
        self._require_legacy_kb_writes_enabled()
        from app.infrastructure.answer_policy import SqlAlchemyAnswerBehaviorProfileRepository

        repo = SqlAlchemyAnswerBehaviorProfileRepository(self._session)
        existing = await repo.find_active_for_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if existing is None:
            raise DomainError.not_found("Answer behavior override not found")
        return await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)

    async def delete_guardrails(self, *, tenant: TenantContext, knowledge_base_id: str) -> bool:
        self._require_admin(tenant)
        self._require_legacy_kb_writes_enabled()
        from app.infrastructure.answer_policy import SqlAlchemyGuardrailProfileRepository

        repo = SqlAlchemyGuardrailProfileRepository(self._session)
        existing = await repo.find_active_for_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if existing is None:
            raise DomainError.not_found("Guardrail override not found")
        return await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)

    async def save_answer_behavior_for_project(
        self,
        *,
        tenant: TenantContext,
        project_id: str,
        version: str,
        persona: str,
        response_style: str,
        max_output_tokens: int,
        source_policy: str,
        greeting_policy: str,
        no_evidence_action: str,
        require_citations: bool,
        allow_mcp_sources: bool,
    ) -> dict[str, object]:
        self._require_admin(tenant)
        await self._require_project(tenant=tenant, project_id=project_id)
        self._validate_output_budget(max_output_tokens)
        try:
            profile = AnswerBehaviorProfile(
                version=version,
                scope=PolicyScope.PROJECT,
                persona=persona,
                response_style=ResponseStyle(response_style),
                max_output_tokens=max_output_tokens,
                source_policy=AnswerSourcePolicy(source_policy),
                greeting_policy=GreetingPolicy(greeting_policy),
                no_evidence_action=NoEvidenceAction(no_evidence_action),
                require_citations=require_citations,
                allow_mcp_sources=allow_mcp_sources,
            )
        except ValueError as exc:
            raise DomainError.validation(str(exc)) from exc
        from app.infrastructure.answer_policy import SqlAlchemyAnswerBehaviorProfileRepository, SqlAlchemyPolicyAuditRepository

        repo = SqlAlchemyAnswerBehaviorProfileRepository(self._session)
        existing = await repo.find_active_for_project(tenant_id=tenant.tenant_id, project_id=project_id)
        if existing:
            await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)
        created = await repo.create(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=None,
            project_id=project_id,
            profile=profile,
            created_by=tenant.user_id,
        )
        await SqlAlchemyPolicyAuditRepository(self._session).record(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            knowledge_base_id=None,
            project_id=project_id,
            policy_kind="ANSWER_BEHAVIOR",
            policy_version=profile.version,
            action="ACTIVATE",
            changes=_answer_behavior_to_dict(profile),
        )
        return _persisted_answer_to_dict(created)

    async def get_answer_behavior_for_project(self, *, tenant: TenantContext, project_id: str) -> dict[str, object]:
        from app.infrastructure.answer_policy import SqlAlchemyAnswerBehaviorProfileRepository

        await self._require_project(tenant=tenant, project_id=project_id)
        value = await SqlAlchemyAnswerBehaviorProfileRepository(self._session).find_active_for_project(
            tenant_id=tenant.tenant_id, project_id=project_id
        )
        if value is None:
            raise DomainError.not_found("Project answer behavior override not found")
        return _persisted_answer_to_dict(value)

    async def save_guardrails_for_project(
        self,
        *,
        tenant: TenantContext,
        project_id: str,
        version: str,
        input_rules: list[str],
        tool_rules: list[str],
        output_rules: list[str],
        max_tool_calls: int,
        max_tool_timeout_seconds: int,
        max_tool_payload_bytes: int,
        max_mcp_freshness_seconds: int,
        require_tool_confirmation: bool,
    ) -> dict[str, object]:
        self._require_admin(tenant)
        await self._require_project(tenant=tenant, project_id=project_id)
        try:
            profile = GuardrailProfile(
                version=version,
                scope=PolicyScope.PROJECT,
                input_rules=tuple(input_rules),
                tool_rules=tuple(tool_rules),
                output_rules=tuple(output_rules),
                max_tool_calls=max_tool_calls,
                max_tool_timeout_seconds=max_tool_timeout_seconds,
                max_tool_payload_bytes=max_tool_payload_bytes,
                max_mcp_freshness_seconds=max_mcp_freshness_seconds,
                require_tool_confirmation=require_tool_confirmation,
            )
        except ValueError as exc:
            raise DomainError.validation(str(exc)) from exc
        from app.infrastructure.answer_policy import SqlAlchemyGuardrailProfileRepository, SqlAlchemyPolicyAuditRepository

        repo = SqlAlchemyGuardrailProfileRepository(self._session)
        existing = await repo.find_active_for_project(tenant_id=tenant.tenant_id, project_id=project_id)
        if existing:
            await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)
        created = await repo.create(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=None,
            project_id=project_id,
            profile=profile,
            created_by=tenant.user_id,
        )
        await SqlAlchemyPolicyAuditRepository(self._session).record(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            knowledge_base_id=None,
            project_id=project_id,
            policy_kind="GUARDRAIL",
            policy_version=profile.version,
            action="ACTIVATE",
            changes=_guardrail_to_dict(profile),
        )
        return _persisted_guardrail_to_dict(created)

    async def get_guardrails_for_project(self, *, tenant: TenantContext, project_id: str) -> dict[str, object]:
        from app.infrastructure.answer_policy import SqlAlchemyGuardrailProfileRepository

        await self._require_project(tenant=tenant, project_id=project_id)
        value = await SqlAlchemyGuardrailProfileRepository(self._session).find_active_for_project(
            tenant_id=tenant.tenant_id, project_id=project_id
        )
        if value is None:
            raise DomainError.not_found("Project guardrail override not found")
        return _persisted_guardrail_to_dict(value)

    async def delete_answer_behavior_for_project(self, *, tenant: TenantContext, project_id: str) -> bool:
        self._require_admin(tenant)
        from app.infrastructure.answer_policy import SqlAlchemyAnswerBehaviorProfileRepository

        await self._require_project(tenant=tenant, project_id=project_id)
        repo = SqlAlchemyAnswerBehaviorProfileRepository(self._session)
        existing = await repo.find_active_for_project(tenant_id=tenant.tenant_id, project_id=project_id)
        if existing is None:
            raise DomainError.not_found("Project answer behavior override not found")
        return await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)

    async def delete_guardrails_for_project(self, *, tenant: TenantContext, project_id: str) -> bool:
        self._require_admin(tenant)
        from app.infrastructure.answer_policy import SqlAlchemyGuardrailProfileRepository

        await self._require_project(tenant=tenant, project_id=project_id)
        repo = SqlAlchemyGuardrailProfileRepository(self._session)
        existing = await repo.find_active_for_project(tenant_id=tenant.tenant_id, project_id=project_id)
        if existing is None:
            raise DomainError.not_found("Project guardrail override not found")
        return await repo.retire(tenant_id=tenant.tenant_id, profile_id=existing.id)

    def get_defaults(self) -> dict[str, object]:
        answer = AnswerBehaviorProfile(version="migrated-default-v1", scope=PolicyScope.DEPLOYMENT)
        guardrails = GuardrailProfile.platform_baseline()
        return {
            "answerBehavior": _answer_behavior_to_dict(answer),
            "guardrails": _guardrail_to_dict(guardrails),
            "deploymentMaxOutputTokens": self._deployment_max_output_tokens,
        }

    @property
    def _deployment_max_output_tokens(self) -> int:
        configured = self._settings.rag_generation_deployment_max_output_tokens
        return configured if configured > 0 else DEFAULT_DEPLOYMENT_MAX_OUTPUT_TOKENS

    def _validate_output_budget(self, max_output_tokens: int) -> None:
        if max_output_tokens > self._deployment_max_output_tokens:
            raise DomainError.validation(
                f"max_output_tokens must be between 128 and {self._deployment_max_output_tokens}"
            )

    def _require_legacy_kb_writes_enabled(self) -> None:
        if not self._settings.rag_project_legacy_kb_writes_enabled:
            raise DomainError(
                "PROJECT_SCOPE_REQUIRED",
                "Project-scoped settings are required; Knowledge Base configuration writes are disabled",
                409,
            )

    async def _require_project(self, *, tenant: TenantContext, project_id: str) -> None:
        from app.infrastructure.rag_projects import SqlAlchemyProjectRepository

        project = await SqlAlchemyProjectRepository(self._session).find_by_id(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
        )
        if project is None or project.status.value != "ACTIVE":
            raise DomainError.not_found("Project not found")

    @staticmethod
    def _require_admin(tenant: TenantContext) -> None:
        if tenant.role is not UserRole.ADMIN:
            raise DomainError.forbidden("Only tenant ADMIN can manage answer policy")


def _answer_behavior_to_dict(profile: AnswerBehaviorProfile) -> dict[str, object]:
    return {
        "version": profile.version,
        "scope": profile.scope.value,
        "persona": profile.persona,
        "responseStyle": profile.response_style.value,
        "maxOutputTokens": profile.max_output_tokens,
        "sourcePolicy": profile.source_policy.value,
        "greetingPolicy": profile.greeting_policy.value,
        "noEvidenceAction": profile.no_evidence_action.value,
        "requireCitations": profile.require_citations,
        "allowMcpSources": profile.allow_mcp_sources,
        "isActive": profile.is_active,
    }


def _guardrail_to_dict(profile: GuardrailProfile) -> dict[str, object]:
    return {
        "version": profile.version,
        "scope": profile.scope.value,
        "inputRules": list(profile.input_rules),
        "toolRules": list(profile.tool_rules),
        "outputRules": list(profile.output_rules),
        "maxToolCalls": profile.max_tool_calls,
        "maxToolTimeoutSeconds": profile.max_tool_timeout_seconds,
        "maxToolPayloadBytes": profile.max_tool_payload_bytes,
        "maxMcpFreshnessSeconds": profile.max_mcp_freshness_seconds,
        "requireToolConfirmation": profile.require_tool_confirmation,
        "isActive": profile.is_active,
    }


def _persisted_answer_to_dict(persisted: PersistedAnswerBehavior) -> dict[str, object]:
    return {
        "id": persisted.id,
        "knowledgeBaseId": persisted.knowledge_base_id,
        "projectId": persisted.project_id,
        **_answer_behavior_to_dict(persisted.profile),
        "createdAt": persisted.created_at.isoformat(),
        "updatedAt": persisted.updated_at.isoformat(),
    }


def _persisted_guardrail_to_dict(persisted: PersistedGuardrailProfile) -> dict[str, object]:
    return {
        "id": persisted.id,
        "knowledgeBaseId": persisted.knowledge_base_id,
        "projectId": persisted.project_id,
        **_guardrail_to_dict(persisted.profile),
        "createdAt": persisted.created_at.isoformat(),
        "updatedAt": persisted.updated_at.isoformat(),
    }
