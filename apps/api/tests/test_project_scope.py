from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.application.answer_policy_service import AnswerPolicyService
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import PolicyScope, ProjectStatus
from app.domain.rag.answer_policy import (
    AnswerBehaviorProfile,
    GuardrailProfile,
    PersistedAnswerBehavior,
    PersistedGuardrailProfile,
)
from app.domain.tenant_context import TenantContext

TENANT_ID = "tenant-1"
OTHER_TENANT_ID = "tenant-2"


def _tenant(tenant_id: str = TENANT_ID) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, membership_id="membership-1", user_id="user-1")


def _project(project_id: str, tenant_id: str = TENANT_ID, status: ProjectStatus = ProjectStatus.ACTIVE) -> SimpleNamespace:
    return SimpleNamespace(id=project_id, tenant_id=tenant_id, slug=project_id, name=project_id, status=status)


def _answer(
    version: str,
    scope: PolicyScope,
    knowledge_base_id: str | None = None,
    project_id: str | None = None,
) -> PersistedAnswerBehavior:
    now = datetime.now(UTC).replace(tzinfo=None)
    return PersistedAnswerBehavior(
        id=f"answer-{version}",
        tenant_id=TENANT_ID,
        knowledge_base_id=knowledge_base_id,
        project_id=project_id,
        profile=AnswerBehaviorProfile(version=version, scope=scope),
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )


def _guardrail(
    version: str,
    scope: PolicyScope,
    knowledge_base_id: str | None = None,
    project_id: str | None = None,
) -> PersistedGuardrailProfile:
    now = datetime.now(UTC).replace(tzinfo=None)
    return PersistedGuardrailProfile(
        id=f"guardrail-{version}",
        tenant_id=TENANT_ID,
        knowledge_base_id=knowledge_base_id,
        project_id=project_id,
        profile=GuardrailProfile(version=version, scope=scope),
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )


class _ProjectRepository:
    def __init__(self, projects: dict[tuple[str, str], SimpleNamespace], resolved: SimpleNamespace | None) -> None:
        self.projects = projects
        self.resolved = resolved
        self.resolve_calls: list[tuple[str, tuple[str, ...]]] = []

    async def find_by_id(self, *, tenant_id: str, project_id: str) -> SimpleNamespace | None:
        return self.projects.get((tenant_id, project_id))

    async def resolve_project_for_knowledge_bases(
        self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]
    ) -> SimpleNamespace | None:
        self.resolve_calls.append((tenant_id, knowledge_base_ids))
        if self.resolved is None or self.resolved.tenant_id != tenant_id:
            return None
        return self.resolved


class _AnswerRepository:
    def __init__(self, *, project: PersistedAnswerBehavior | None = None, legacy: PersistedAnswerBehavior | None = None) -> None:
        self.project = project
        self.legacy = legacy
        self.legacy_calls = 0

    async def find_active_deployment(self, *, tenant_id: str) -> PersistedAnswerBehavior:
        return _answer("deployment", PolicyScope.DEPLOYMENT)

    async def find_active_for_project(self, *, tenant_id: str, project_id: str) -> PersistedAnswerBehavior | None:
        return self.project

    async def find_active_for_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> PersistedAnswerBehavior | None:
        self.legacy_calls += 1
        return self.legacy


class _GuardrailRepository:
    def __init__(
        self,
        *,
        project: PersistedGuardrailProfile | None = None,
        legacy: PersistedGuardrailProfile | None = None,
    ) -> None:
        self.project = project
        self.legacy = legacy
        self.legacy_calls = 0

    async def find_active_deployment(self, *, tenant_id: str) -> PersistedGuardrailProfile:
        return _guardrail("deployment", PolicyScope.DEPLOYMENT)

    async def find_active_for_project(self, *, tenant_id: str, project_id: str) -> PersistedGuardrailProfile | None:
        return self.project

    async def find_active_for_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> PersistedGuardrailProfile | None:
        self.legacy_calls += 1
        return self.legacy


def _service(
    *,
    project_repo: _ProjectRepository,
    answer_repo: _AnswerRepository,
    guardrail_repo: _GuardrailRepository,
    fallback_enabled: bool = True,
) -> tuple[AnswerPolicyService, ExitStack]:
    service = AnswerPolicyService(
        object(),
        Settings(_env_file=None, rag_project_legacy_fallback_enabled=fallback_enabled),
    )
    patches = ExitStack()
    patches.enter_context(patch("app.infrastructure.rag_projects.SqlAlchemyProjectRepository", return_value=project_repo))
    patches.enter_context(
        patch("app.infrastructure.answer_policy.SqlAlchemyAnswerBehaviorProfileRepository", return_value=answer_repo)
    )
    patches.enter_context(
        patch("app.infrastructure.answer_policy.SqlAlchemyGuardrailProfileRepository", return_value=guardrail_repo)
    )
    return service, patches


@pytest.mark.asyncio
async def test_one_kb_inference_and_multi_kb_same_project_share_one_scope() -> None:
    project = _project("project-a")
    project_repo = _ProjectRepository({(TENANT_ID, project.id): project}, project)
    answer_repo = _AnswerRepository(project=_answer("project", PolicyScope.PROJECT, project_id=project.id))
    guardrail_repo = _GuardrailRepository(project=_guardrail("project", PolicyScope.PROJECT, project_id=project.id))
    service, patches = _service(project_repo=project_repo, answer_repo=answer_repo, guardrail_repo=guardrail_repo)
    try:
        one_kb = await service.resolve_effective(tenant=_tenant(), knowledge_base_ids=("kb-1",))
        multi_kb = await service.resolve_effective(tenant=_tenant(), knowledge_base_ids=("kb-1", "kb-2"))
    finally:
        patches.close()

    assert one_kb.answer_behavior_version == "project"
    assert multi_kb.answer_behavior_version == "project"
    assert project_repo.resolve_calls == [(TENANT_ID, ("kb-1",)), (TENANT_ID, ("kb-1", "kb-2"))]


@pytest.mark.asyncio
async def test_explicit_project_mismatch_fails_before_policy_resolution() -> None:
    project_a = _project("project-a")
    project_b = _project("project-b")
    project_repo = _ProjectRepository(
        {(TENANT_ID, project_a.id): project_a, (TENANT_ID, project_b.id): project_b},
        project_b,
    )
    service, patches = _service(
        project_repo=project_repo,
        answer_repo=_AnswerRepository(),
        guardrail_repo=_GuardrailRepository(),
    )
    try:
        with pytest.raises(DomainError) as error:
            await service.resolve_effective(tenant=_tenant(), project_id=project_a.id, knowledge_base_ids=("kb-1",))
    finally:
        patches.close()

    assert error.value.code == "PROJECT_SCOPE_CONFLICT"
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_cross_tenant_project_id_and_archived_project_fail_closed() -> None:
    foreign_project = _project("project-foreign", tenant_id=OTHER_TENANT_ID)
    archived_project = _project("project-archived", status=ProjectStatus.ARCHIVED)
    for project in (foreign_project, archived_project):
        project_repo = _ProjectRepository({(project.tenant_id, project.id): project}, project)
        service, patches = _service(
            project_repo=project_repo,
            answer_repo=_AnswerRepository(),
            guardrail_repo=_GuardrailRepository(),
        )
        try:
            with pytest.raises(DomainError) as error:
                await service.resolve_effective(tenant=_tenant(), project_id=project.id, knowledge_base_ids=("kb-1",))
        finally:
            patches.close()
        assert error.value.code == "NOT_FOUND"
        assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_legacy_fallback_is_single_kb_only_and_flagged() -> None:
    project = _project("project-a")
    project_repo = _ProjectRepository({(TENANT_ID, project.id): project}, project)
    answer_repo = _AnswerRepository(legacy=_answer("legacy", PolicyScope.KNOWLEDGE_BASE, knowledge_base_id="kb-1"))
    guardrail_repo = _GuardrailRepository(
        legacy=_guardrail("legacy", PolicyScope.KNOWLEDGE_BASE, knowledge_base_id="kb-1")
    )
    service, patches = _service(project_repo=project_repo, answer_repo=answer_repo, guardrail_repo=guardrail_repo)
    try:
        single_kb = await service.resolve_effective(tenant=_tenant(), knowledge_base_ids=("kb-1",))
        multi_kb = await service.resolve_effective(tenant=_tenant(), knowledge_base_ids=("kb-1", "kb-2"))
    finally:
        patches.close()

    assert single_kb.answer_behavior_version == "legacy"
    assert multi_kb.answer_behavior_version == "deployment"
    assert answer_repo.legacy_calls == 1
    assert guardrail_repo.legacy_calls == 1

