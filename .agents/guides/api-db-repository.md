# Guide: API SQLAlchemy Repository (`apps/api/app/infrastructure/database.py`)

## Folder Contract

✅ Allowed:
- Implement repository Protocol from `domain/repositories.py`
- Access SQLAlchemy `AsyncSession`
- Map ORM record to domain Entity via `_to_*` mapper function

❌ Forbidden:
- Business logic
- Return raw ORM record — always map to Entity
- HTTP concerns

---

## Conventions

### ORM Record Pattern

```python
# infrastructure/database.py
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
```

### Repository Implementation

```python
# infrastructure/database.py
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserRecord).where(UserRecord.email == email))
        row = result.scalar_one_or_none()
        return _to_user(row) if row else None

    async def create(self, *, email: str, password_hash: str, name: str, role: UserRole, status: UserStatus, photo: str | None) -> User:
        row = UserRecord(id=str(uuid4()), email=email, password_hash=password_hash, name=name, role=role, status=status, photo=photo)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_user(row)

    async def delete(self, user_id: str) -> None:
        await self._session.execute(delete(UserRecord).where(UserRecord.id == user_id))
        await self._session.commit()
```

### Entity Mapper

```python
def _to_user(row: UserRecord) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        name=row.name,
        role=row.role,
        status=row.status,
        photo=row.photo,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
```

### Session Factory

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(settings.async_database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session
```

### Naming

- File name: `database.py` (single file for all records + repos) or split to `database/{domain}.py` when it grows
- ORM record class: `{Domain}Record` — PascalCase with `Record` suffix
- Repository class: `SqlAlchemy{Domain}Repository` — PascalCase with `SqlAlchemy` prefix
- Mapper function: `_to_{domain}` — private, snake_case

---

## Additional Rules

- `_to_*` mapper is written as a private function (underscore prefix) — no need to export
- Use `select()` for queries (SQLAlchemy 2.0 style) — not the legacy `query()` API
- Use `mapped_column` with explicit snake_case column names via first positional arg
- Use `Enum(PythonEnum)` for enum columns — the Python `StrEnum` is the source of truth
- ORM record is the persistence model — Entity is the domain model; they are separate types
- File must end with newline
