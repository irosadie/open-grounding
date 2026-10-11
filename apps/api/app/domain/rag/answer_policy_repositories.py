"""Repository protocols for answer behavior and guardrail policy versions."""

from typing import Protocol

from app.domain.rag.answer_policy import (
    AnswerBehaviorProfile,
    GuardrailProfile,
    PersistedAnswerBehavior,
    PersistedGuardrailProfile,
)


class AnswerBehaviorProfileRepository(Protocol):
    async def find_active_deployment(self, *, tenant_id: str) -> PersistedAnswerBehavior | None: ...

    async def find_active_for_knowledge_base(
        self, *, tenant_id: str, knowledge_base_id: str
    ) -> PersistedAnswerBehavior | None: ...
    async def find_active_for_project(self, *, tenant_id: str, project_id: str) -> PersistedAnswerBehavior | None: ...

    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str | None,
        profile: AnswerBehaviorProfile,
        created_by: str | None,
        project_id: str | None = None,
    ) -> PersistedAnswerBehavior: ...

    async def retire(self, *, tenant_id: str, profile_id: str) -> bool: ...


class GuardrailProfileRepository(Protocol):
    async def find_active_deployment(self, *, tenant_id: str) -> PersistedGuardrailProfile | None: ...

    async def find_active_for_knowledge_base(
        self, *, tenant_id: str, knowledge_base_id: str
    ) -> PersistedGuardrailProfile | None: ...
    async def find_active_for_project(self, *, tenant_id: str, project_id: str) -> PersistedGuardrailProfile | None: ...

    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str | None,
        profile: GuardrailProfile,
        created_by: str | None,
        project_id: str | None = None,
    ) -> PersistedGuardrailProfile: ...

    async def retire(self, *, tenant_id: str, profile_id: str) -> bool: ...


class PolicyAuditRepository(Protocol):
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
    ) -> None: ...
