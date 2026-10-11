from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class TenantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class TenantMembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PolicyScope(StrEnum):
    DEPLOYMENT = "DEPLOYMENT"
    TENANT = "TENANT"
    PROJECT = "PROJECT"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class ProjectMigrationReview:
    id: str
    tenant_id: str
    project_id: str
    knowledge_base_id: str | None
    config_kind: str
    status: str
    legacy_count: int
    created_at: datetime
    updated_at: datetime


class AnswerSourcePolicy(StrEnum):
    DOCUMENT_ONLY = "DOCUMENT_ONLY"
    DOCUMENT_OR_MCP = "DOCUMENT_OR_MCP"
    DOCUMENT_MCP_GENERAL = "DOCUMENT_MCP_GENERAL"


class GreetingPolicy(StrEnum):
    ALLOW_UNGROUNDED = "ALLOW_UNGROUNDED"
    REQUIRE_ALLOWED_SOURCE = "REQUIRE_ALLOWED_SOURCE"
    REFUSE = "REFUSE"


class NoEvidenceAction(StrEnum):
    ABSTAIN = "ABSTAIN"
    REFUSE = "REFUSE"
    ANSWER_UNGROUNDED = "ANSWER_UNGROUNDED"


class ResponseStyle(StrEnum):
    CONCISE = "CONCISE"
    BALANCED = "BALANCED"
    DETAILED = "DETAILED"


class ProvenanceKind(StrEnum):
    DOCUMENT = "DOCUMENT"
    MCP = "MCP"


class GuardrailStage(StrEnum):
    INPUT = "INPUT"
    TOOL = "TOOL"
    OUTPUT = "OUTPUT"


class GuardrailDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REDACT = "REDACT"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    FAIL_CLOSED = "FAIL_CLOSED"


@dataclass(frozen=True)
class User:
    id: str
    email: str
    password_hash: str
    name: str
    role: UserRole
    status: UserStatus
    photo: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AuthSession:
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class Tenant:
    id: str
    slug: str
    name: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TenantMembership:
    id: str
    tenant_id: str
    user_id: str
    status: TenantMembershipStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Project:
    id: str
    tenant_id: str
    slug: str
    name: str
    status: ProjectStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime
