from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.settings import Settings, get_settings
from app.domain.models import (
    AuthSession,
    Tenant,
    TenantMembership,
    TenantMembershipStatus,
    TenantStatus,
    User,
    UserRole,
    UserStatus,
)


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column("password_hash", String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="UserRole"), default=UserRole.USER, nullable=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, name="UserStatus"), default=UserStatus.ACTIVE, nullable=False)
    photo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=False),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    auth_sessions: Mapped[list["AuthSessionRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tenant_memberships: Mapped[list["TenantMembershipRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        "user_id",
        Uuid(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column("token_hash", String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column("expires_at", DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    user: Mapped[UserRecord] = relationship(back_populates="auth_sessions")


class TenantRecord(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="TenantStatus"),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=False),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    memberships: Mapped[list["TenantMembershipRecord"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantMembershipRecord(Base):
    __tablename__ = "tenant_memberships"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        "tenant_id",
        Uuid(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        "user_id",
        Uuid(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[TenantMembershipStatus] = mapped_column(
        Enum(TenantMembershipStatus, name="TenantMembershipStatus"),
        default=TenantMembershipStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=False),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    tenant: Mapped[TenantRecord] = relationship(back_populates="memberships")
    user: Mapped[UserRecord] = relationship(back_populates="tenant_memberships")


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = create_session_factory(get_settings())
    async with session_factory() as session:
        yield session


class SqlAlchemyAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_user_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserRecord).where(UserRecord.email == email))
        row = result.scalar_one_or_none()
        return _to_user(row) if row else None

    async def find_user_by_id(self, user_id: str) -> User | None:
        result = await self._session.execute(select(UserRecord).where(UserRecord.id == user_id))
        row = result.scalar_one_or_none()
        return _to_user(row) if row else None

    async def create_user(self, *, email: str, password_hash: str, name: str, role: UserRole, status: UserStatus, photo: str | None) -> User:
        row = UserRecord(id=str(uuid4()), email=email, password_hash=password_hash, name=name, role=role, status=status, photo=photo)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_user(row)

    async def create_auth_session(self, *, session_id: str, user_id: str, token_hash: str, expires_at: datetime) -> AuthSession:
        row = AuthSessionRecord(id=session_id, user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_session(row)

    async def find_auth_session(self, session_id: str, user_id: str) -> AuthSession | None:
        result = await self._session.execute(
            select(AuthSessionRecord).where(
                AuthSessionRecord.id == session_id,
                AuthSessionRecord.user_id == user_id,
                AuthSessionRecord.expires_at > utc_now(),
            )
        )
        row = result.scalar_one_or_none()
        return _to_session(row) if row else None

    async def delete_auth_session(self, session_id: str, user_id: str) -> None:
        await self._session.execute(delete(AuthSessionRecord).where(AuthSessionRecord.id == session_id, AuthSessionRecord.user_id == user_id))
        await self._session.commit()

    async def delete_auth_sessions_for_user(self, user_id: str) -> None:
        await self._session.execute(delete(AuthSessionRecord).where(AuthSessionRecord.user_id == user_id))
        await self._session.commit()


class SqlAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_tenant_by_id(self, tenant_id: str) -> Tenant | None:
        result = await self._session.execute(select(TenantRecord).where(TenantRecord.id == tenant_id))
        row = result.scalar_one_or_none()
        return _to_tenant(row) if row else None

    async def find_active_tenant(self) -> Tenant | None:
        result = await self._session.execute(
            select(TenantRecord).where(TenantRecord.status == TenantStatus.ACTIVE).order_by(TenantRecord.created_at).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_tenant(row) if row else None

    async def create_tenant(self, *, tenant_id: str, slug: str, name: str) -> Tenant:
        row = TenantRecord(id=tenant_id, slug=slug, name=name, status=TenantStatus.ACTIVE)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_tenant(row)

    async def find_membership(self, *, tenant_id: str, user_id: str) -> TenantMembership | None:
        result = await self._session.execute(
            select(TenantMembershipRecord).where(
                TenantMembershipRecord.tenant_id == tenant_id,
                TenantMembershipRecord.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_membership(row) if row else None

    async def create_membership(
        self, *, tenant_id: str, user_id: str, status: TenantMembershipStatus
    ) -> TenantMembership:
        row = TenantMembershipRecord(id=str(uuid4()), tenant_id=tenant_id, user_id=user_id, status=status)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_membership(row)

    async def find_active_membership(self, *, tenant_id: str, user_id: str) -> TenantMembership | None:
        result = await self._session.execute(
            select(TenantMembershipRecord).where(
                TenantMembershipRecord.tenant_id == tenant_id,
                TenantMembershipRecord.user_id == user_id,
                TenantMembershipRecord.status == TenantMembershipStatus.ACTIVE,
            )
        )
        row = result.scalar_one_or_none()
        return _to_membership(row) if row else None

    async def backfill_memberships(self, *, tenant_id: str, status: TenantMembershipStatus) -> int:
        """Create memberships for users who do not yet have one in this tenant.

        Uses a single INSERT…SELECT so it is atomic and idempotent. Existing
        user IDs, password hashes, and auth-session identifiers are never
        modified.
        """
        result = await self._session.execute(
            text(
                """
                INSERT INTO tenant_memberships (id, tenant_id, user_id, status, created_at, updated_at)
                SELECT gen_random_uuid(), :tenant_id, u.id, CAST(:status AS "TenantMembershipStatus"), now(), now()
                FROM users u
                WHERE NOT EXISTS (
                    SELECT 1 FROM tenant_memberships tm
                    WHERE tm.tenant_id = CAST(:tenant_id AS uuid) AND tm.user_id = u.id
                )
                """
            ),
            {"tenant_id": tenant_id, "status": status.value},
        )
        await self._session.commit()
        return cast(int, getattr(result, "rowcount", 0) or 0)


def _to_user(row: UserRecord) -> User:
    return User(id=row.id, email=row.email, password_hash=row.password_hash, name=row.name, role=row.role, status=row.status, photo=row.photo, created_at=row.created_at, updated_at=row.updated_at)


def _to_session(row: AuthSessionRecord) -> AuthSession:
    return AuthSession(id=row.id, user_id=row.user_id, token_hash=row.token_hash, expires_at=row.expires_at, created_at=row.created_at)


def _to_tenant(row: TenantRecord) -> Tenant:
    return Tenant(id=row.id, slug=row.slug, name=row.name, status=row.status, created_at=row.created_at, updated_at=row.updated_at)


def _to_membership(row: TenantMembershipRecord) -> TenantMembership:
    return TenantMembership(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
