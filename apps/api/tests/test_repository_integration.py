import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.domain.models import UserRole, UserStatus
from app.infrastructure.database import (
    AuthSessionRecord,
    SqlAlchemyAuthRepository,
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
        await session.execute(delete(AuthSessionRecord))
        await session.execute(delete(UserRecord))
        await session.commit()
        yield SqlAlchemyAuthRepository(session)
    bind = session_factory.kw.get("bind")
    if bind is not None:
        await bind.dispose()


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
