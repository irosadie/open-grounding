import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.domain.models import TenantMembershipStatus, UserRole, UserStatus
from app.infrastructure.database import (
    AuthSessionRecord,
    SqlAlchemyAuthRepository,
    SqlAlchemyTenantRepository,
    TenantMembershipRecord,
    TenantRecord,
    UserRecord,
    create_session_factory,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Set RUN_DATABASE_TESTS=1 to run PostgreSQL integration tests.",
)


@pytest.fixture
async def repository() -> SqlAlchemyAuthRepository:
    settings = Settings()
    database_name = urlparse(settings.database_url).path.removeprefix("/")
    if not database_name.endswith("_test"):
        raise RuntimeError("Integration tests require a DATABASE_URL ending in _test.")

    session_factory: async_sessionmaker[AsyncSession] = create_session_factory(settings)
    async with session_factory() as session:
        await session.execute(delete(TenantMembershipRecord))
        await session.execute(delete(TenantRecord))
        await session.execute(delete(AuthSessionRecord))
        await session.execute(delete(UserRecord))
        await session.commit()
        yield SqlAlchemyAuthRepository(session)
    bind = session_factory.kw.get("bind")
    if bind is not None:
        await bind.dispose()


@pytest.fixture
async def tenant_repository(repository: SqlAlchemyAuthRepository) -> SqlAlchemyTenantRepository:
    return SqlAlchemyTenantRepository(repository._session)


DEPLOYMENT_TENANT_ID = str(uuid4())


async def test_repository_persists_user_and_session(
    repository: SqlAlchemyAuthRepository,
) -> None:
    user = await repository.create_user(
        email="integration@example.com",
        password_hash="legacy-scrypt-hash",
        name="Integration User",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        photo=None,
    )
    session = await repository.create_auth_session(
        session_id=str(uuid4()),
        user_id=user.id,
        token_hash="refresh-token-hash",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None),
    )

    persisted_user = await repository.find_user_by_email(user.email)
    persisted_session = await repository.find_auth_session(session.id, user.id)

    assert persisted_user == user
    assert persisted_session == session

    await repository.delete_auth_session(session.id, user.id)

    assert await repository.find_auth_session(session.id, user.id) is None


async def test_repository_reads_existing_row_and_manages_session_lifecycle(
    repository: SqlAlchemyAuthRepository,
) -> None:
    user_id = str(uuid4())
    created_at = datetime.now(UTC).replace(tzinfo=None)

    await repository._session.execute(
        text(
            """
            INSERT INTO users (
                id, email, password_hash, name, role, status, photo, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), :email, :password_hash, :name,
                CAST(:role AS \"UserRole\"), CAST(:status AS \"UserStatus\"), :photo,
                :created_at, :updated_at
            )
            """
        ),
        {
            "id": user_id,
            "email": "legacy@example.com",
            "password_hash": "legacy-scrypt-hash",
            "name": "Legacy User",
            "role": UserRole.ADMIN.value,
            "status": UserStatus.ACTIVE.value,
            "photo": None,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    await repository._session.commit()

    existing_user = await repository.find_user_by_email("legacy@example.com")

    assert existing_user is not None
    assert existing_user.id == user_id
    assert existing_user.role is UserRole.ADMIN
    assert existing_user.status is UserStatus.ACTIVE

    session = await repository.create_auth_session(
        session_id=str(uuid4()),
        user_id=existing_user.id,
        token_hash="refresh-token-hash",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None),
    )

    assert await repository.find_auth_session(session.id, existing_user.id) == session

    await repository.delete_auth_sessions_for_user(existing_user.id)

    assert await repository.find_auth_session(session.id, existing_user.id) is None


async def test_tenant_bootstrap_creates_tenant_and_backfills_memberships(
    repository: SqlAlchemyAuthRepository,
    tenant_repository: SqlAlchemyTenantRepository,
) -> None:
    user_a = await repository.create_user(
        email="user-a@example.com",
        password_hash="hash-a",
        name="User A",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        photo=None,
    )
    user_b = await repository.create_user(
        email="user-b@example.com",
        password_hash="hash-b",
        name="User B",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        photo=None,
    )

    assert await tenant_repository.find_tenant_by_id(DEPLOYMENT_TENANT_ID) is None

    tenant = await tenant_repository.create_tenant(
        tenant_id=DEPLOYMENT_TENANT_ID,
        slug="deployment-test",
        name="Test Deployment Tenant",
    )
    assert tenant.id == DEPLOYMENT_TENANT_ID
    assert tenant.status.value == "ACTIVE"

    backfilled = await tenant_repository.backfill_memberships(
        tenant_id=DEPLOYMENT_TENANT_ID,
        status=TenantMembershipStatus.ACTIVE,
    )
    assert backfilled == 2

    membership_a = await tenant_repository.find_active_membership(
        tenant_id=DEPLOYMENT_TENANT_ID,
        user_id=user_a.id,
    )
    membership_b = await tenant_repository.find_active_membership(
        tenant_id=DEPLOYMENT_TENANT_ID,
        user_id=user_b.id,
    )
    assert membership_a is not None and membership_a.status is TenantMembershipStatus.ACTIVE
    assert membership_b is not None and membership_b.status is TenantMembershipStatus.ACTIVE

    # Idempotency: re-running backfill creates zero new memberships.
    assert (
        await tenant_repository.backfill_memberships(
            tenant_id=DEPLOYMENT_TENANT_ID,
            status=TenantMembershipStatus.ACTIVE,
        )
        == 0
    )


async def test_tenant_membership_backfill_preserves_user_and_session_identifiers(
    repository: SqlAlchemyAuthRepository,
    tenant_repository: SqlAlchemyTenantRepository,
) -> None:
    user = await repository.create_user(
        email="preserve@example.com",
        password_hash="original-hash",
        name="Preserve User",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        photo=None,
    )
    session = await repository.create_auth_session(
        session_id=str(uuid4()),
        user_id=user.id,
        token_hash="original-session-hash",
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )

    await tenant_repository.create_tenant(
        tenant_id=DEPLOYMENT_TENANT_ID,
        slug="preserve-test",
        name="Preserve Test Tenant",
    )
    await tenant_repository.backfill_memberships(
        tenant_id=DEPLOYMENT_TENANT_ID,
        status=TenantMembershipStatus.ACTIVE,
    )

    persisted_user = await repository.find_user_by_id(user.id)
    assert persisted_user is not None and persisted_user.password_hash == "original-hash"

    persisted_session = await repository.find_auth_session(session.id, user.id)
    assert persisted_session is not None and persisted_session.token_hash == "original-session-hash"


async def test_tenant_mismatch_detected_on_existing_active_tenant(
    repository: SqlAlchemyAuthRepository,
    tenant_repository: SqlAlchemyTenantRepository,
) -> None:
    existing_tenant_id = str(uuid4())
    await tenant_repository.create_tenant(
        tenant_id=existing_tenant_id,
        slug="existing-tenant",
        name="Existing Tenant",
    )

    # A different configured ID does not find a match.
    assert await tenant_repository.find_tenant_by_id(DEPLOYMENT_TENANT_ID) is None

    active = await tenant_repository.find_active_tenant()
    assert active is not None and active.id == existing_tenant_id


async def test_cross_tenant_membership_isolation(
    repository: SqlAlchemyAuthRepository,
    tenant_repository: SqlAlchemyTenantRepository,
) -> None:
    tenant_a_id = str(uuid4())
    tenant_b_id = str(uuid4())

    await tenant_repository.create_tenant(tenant_id=tenant_a_id, slug="tenant-a", name="Tenant A")
    await tenant_repository.create_tenant(tenant_id=tenant_b_id, slug="tenant-b", name="Tenant B")

    user = await repository.create_user(
        email="cross-tenant@example.com",
        password_hash="hash",
        name="Cross Tenant User",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        photo=None,
    )

    await tenant_repository.create_membership(
        tenant_id=tenant_a_id,
        user_id=user.id,
        status=TenantMembershipStatus.ACTIVE,
    )

    assert (
        await tenant_repository.find_active_membership(
            tenant_id=tenant_a_id,
            user_id=user.id,
        )
        is not None
    )
    assert (
        await tenant_repository.find_active_membership(
            tenant_id=tenant_b_id,
            user_id=user.id,
        )
        is None
    )
