"""SQLAlchemy records for versioned answer behavior and guardrail profiles."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models import (
    AnswerSourcePolicy,
    GreetingPolicy,
    NoEvidenceAction,
    PolicyScope,
    ResponseStyle,
)
from app.domain.rag.answer_policy import (
    AnswerBehaviorProfile,
    GuardrailProfile,
    PersistedAnswerBehavior,
    PersistedGuardrailProfile,
)
from app.infrastructure.database import Base, utc_now


class AnswerBehaviorProfileRecord(Base):
    __tablename__ = "rag_answer_behavior_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_projects.id", ondelete="CASCADE"), nullable=True
    )
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"),
        nullable=True,
    )
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[PolicyScope] = mapped_column(
        Enum(PolicyScope, name="PolicyScope", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    persona: Mapped[str] = mapped_column(Text, default="", nullable=False)
    response_style: Mapped[ResponseStyle] = mapped_column(
        Enum(ResponseStyle, name="ResponseStyle", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    source_policy: Mapped[AnswerSourcePolicy] = mapped_column(
        Enum(AnswerSourcePolicy, name="AnswerSourcePolicy", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    greeting_policy: Mapped[GreetingPolicy] = mapped_column(
        Enum(GreetingPolicy, name="GreetingPolicy", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    no_evidence_action: Mapped[NoEvidenceAction] = mapped_column(
        Enum(NoEvidenceAction, name="NoEvidenceAction", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    require_citations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_mcp_sources: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope", "knowledge_base_id", "version", name="uq_rag_answer_behavior_scope_version"),
        Index("ix_rag_answer_behavior_tenant_active", "tenant_id", "is_active"),
        Index("ix_rag_answer_behavior_tenant_kb", "tenant_id", "knowledge_base_id"),
        Index("ix_rag_answer_behavior_tenant_project", "tenant_id", "project_id"),
    )


class GuardrailProfileRecord(Base):
    __tablename__ = "rag_guardrail_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_projects.id", ondelete="CASCADE"), nullable=True
    )
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"),
        nullable=True,
    )
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[PolicyScope] = mapped_column(
        Enum(PolicyScope, name="PolicyScope", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    input_rules: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tool_rules: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    output_rules: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tool_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tool_payload_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_mcp_freshness_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    require_tool_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope", "knowledge_base_id", "version", name="uq_rag_guardrail_scope_version"),
        Index("ix_rag_guardrail_tenant_active", "tenant_id", "is_active"),
        Index("ix_rag_guardrail_tenant_kb", "tenant_id", "knowledge_base_id"),
        Index("ix_rag_guardrail_tenant_project", "tenant_id", "project_id"),
    )


class PolicyAuditEventRecord(Base):
    __tablename__ = "rag_policy_audit_events"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_projects.id", ondelete="SET NULL"), nullable=True
    )
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
    )
    policy_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_rag_policy_audit_tenant_created", "tenant_id", "created_at"),
        Index("ix_rag_policy_audit_tenant_kind", "tenant_id", "policy_kind"),
        Index("ix_rag_policy_audit_tenant_project", "tenant_id", "project_id"),
    )


class SqlAlchemyAnswerBehaviorProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_active_deployment(self, *, tenant_id: str) -> PersistedAnswerBehavior | None:
        result = await self._session.execute(
            select(AnswerBehaviorProfileRecord).where(
                AnswerBehaviorProfileRecord.tenant_id == tenant_id,
                AnswerBehaviorProfileRecord.scope == PolicyScope.DEPLOYMENT,
                AnswerBehaviorProfileRecord.knowledge_base_id.is_(None),
                AnswerBehaviorProfileRecord.is_active.is_(True),
            ).order_by(AnswerBehaviorProfileRecord.created_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_answer_behavior(row) if row else None

    async def find_active_for_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> PersistedAnswerBehavior | None:
        result = await self._session.execute(
            select(AnswerBehaviorProfileRecord).where(
                AnswerBehaviorProfileRecord.tenant_id == tenant_id,
                AnswerBehaviorProfileRecord.scope == PolicyScope.KNOWLEDGE_BASE,
                AnswerBehaviorProfileRecord.knowledge_base_id == knowledge_base_id,
                AnswerBehaviorProfileRecord.is_active.is_(True),
            ).order_by(AnswerBehaviorProfileRecord.created_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_answer_behavior(row) if row else None

    async def find_active_for_project(self, *, tenant_id: str, project_id: str) -> PersistedAnswerBehavior | None:
        result = await self._session.execute(
            select(AnswerBehaviorProfileRecord).where(
                AnswerBehaviorProfileRecord.tenant_id == tenant_id,
                AnswerBehaviorProfileRecord.scope == PolicyScope.PROJECT,
                AnswerBehaviorProfileRecord.project_id == project_id,
                AnswerBehaviorProfileRecord.is_active.is_(True),
            ).order_by(AnswerBehaviorProfileRecord.created_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_answer_behavior(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str | None,
        profile: AnswerBehaviorProfile,
        created_by: str | None,
        project_id: str | None = None,
    ) -> PersistedAnswerBehavior:
        row = AnswerBehaviorProfileRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            project_id=project_id,
            version=profile.version,
            scope=profile.scope,
            persona=profile.persona,
            response_style=profile.response_style,
            max_output_tokens=profile.max_output_tokens,
            source_policy=profile.source_policy,
            greeting_policy=profile.greeting_policy,
            no_evidence_action=profile.no_evidence_action,
            require_citations=profile.require_citations,
            allow_mcp_sources=profile.allow_mcp_sources,
            is_active=profile.is_active,
            effective_from=profile.effective_from,
            effective_to=profile.effective_to,
            created_by=created_by,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_answer_behavior(row)

    async def retire(self, *, tenant_id: str, profile_id: str) -> bool:
        result = await self._session.execute(
            update(AnswerBehaviorProfileRecord)
            .where(AnswerBehaviorProfileRecord.id == profile_id, AnswerBehaviorProfileRecord.tenant_id == tenant_id)
            .values(is_active=False, updated_at=utc_now())
        )
        await self._session.commit()
        return bool(getattr(result, "rowcount", 0) == 1)


class SqlAlchemyGuardrailProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_active_deployment(self, *, tenant_id: str) -> PersistedGuardrailProfile | None:
        result = await self._session.execute(
            select(GuardrailProfileRecord).where(
                GuardrailProfileRecord.tenant_id == tenant_id,
                GuardrailProfileRecord.scope == PolicyScope.DEPLOYMENT,
                GuardrailProfileRecord.knowledge_base_id.is_(None),
                GuardrailProfileRecord.is_active.is_(True),
            ).order_by(GuardrailProfileRecord.created_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_guardrail_profile(row) if row else None

    async def find_active_for_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> PersistedGuardrailProfile | None:
        result = await self._session.execute(
            select(GuardrailProfileRecord).where(
                GuardrailProfileRecord.tenant_id == tenant_id,
                GuardrailProfileRecord.scope == PolicyScope.KNOWLEDGE_BASE,
                GuardrailProfileRecord.knowledge_base_id == knowledge_base_id,
                GuardrailProfileRecord.is_active.is_(True),
            ).order_by(GuardrailProfileRecord.created_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_guardrail_profile(row) if row else None

    async def find_active_for_project(self, *, tenant_id: str, project_id: str) -> PersistedGuardrailProfile | None:
        result = await self._session.execute(
            select(GuardrailProfileRecord).where(
                GuardrailProfileRecord.tenant_id == tenant_id,
                GuardrailProfileRecord.scope == PolicyScope.PROJECT,
                GuardrailProfileRecord.project_id == project_id,
                GuardrailProfileRecord.is_active.is_(True),
            ).order_by(GuardrailProfileRecord.created_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_guardrail_profile(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str | None,
        profile: GuardrailProfile,
        created_by: str | None,
        project_id: str | None = None,
    ) -> PersistedGuardrailProfile:
        row = GuardrailProfileRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            project_id=project_id,
            version=profile.version,
            scope=profile.scope,
            input_rules=list(profile.input_rules),
            tool_rules=list(profile.tool_rules),
            output_rules=list(profile.output_rules),
            max_tool_calls=profile.max_tool_calls,
            max_tool_timeout_seconds=profile.max_tool_timeout_seconds,
            max_tool_payload_bytes=profile.max_tool_payload_bytes,
            max_mcp_freshness_seconds=profile.max_mcp_freshness_seconds,
            require_tool_confirmation=profile.require_tool_confirmation,
            is_active=profile.is_active,
            created_by=created_by,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_guardrail_profile(row)

    async def retire(self, *, tenant_id: str, profile_id: str) -> bool:
        result = await self._session.execute(
            update(GuardrailProfileRecord)
            .where(GuardrailProfileRecord.id == profile_id, GuardrailProfileRecord.tenant_id == tenant_id)
            .values(is_active=False, updated_at=utc_now())
        )
        await self._session.commit()
        return bool(getattr(result, "rowcount", 0) == 1)


class SqlAlchemyPolicyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        knowledge_base_id: str | None,
        policy_kind: str,
        policy_version: str,
        action: str,
        changes: dict[str, object],
        trace_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self._session.add(
            PolicyAuditEventRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                project_id=project_id,
                policy_kind=policy_kind,
                policy_version=policy_version,
                action=action,
                changes=changes,
                trace_id=trace_id,
            )
        )
        await self._session.commit()


def _to_answer_behavior(row: AnswerBehaviorProfileRecord) -> PersistedAnswerBehavior:
    return PersistedAnswerBehavior(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        profile=AnswerBehaviorProfile(
            version=row.version,
            scope=row.scope,
            persona=row.persona,
            response_style=row.response_style,
            max_output_tokens=row.max_output_tokens,
            source_policy=row.source_policy,
            greeting_policy=row.greeting_policy,
            no_evidence_action=row.no_evidence_action,
            require_citations=row.require_citations,
            allow_mcp_sources=row.allow_mcp_sources,
            is_active=row.is_active,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        ),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        project_id=row.project_id,
    )


def _to_guardrail_profile(row: GuardrailProfileRecord) -> PersistedGuardrailProfile:
    return PersistedGuardrailProfile(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        profile=GuardrailProfile(
            version=row.version,
            scope=row.scope,
            input_rules=tuple(row.input_rules),
            tool_rules=tuple(row.tool_rules),
            output_rules=tuple(row.output_rules),
            max_tool_calls=row.max_tool_calls,
            max_tool_timeout_seconds=row.max_tool_timeout_seconds,
            max_tool_payload_bytes=row.max_tool_payload_bytes,
            max_mcp_freshness_seconds=row.max_mcp_freshness_seconds,
            require_tool_confirmation=row.require_tool_confirmation,
            is_active=row.is_active,
        ),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        project_id=row.project_id,
    )
