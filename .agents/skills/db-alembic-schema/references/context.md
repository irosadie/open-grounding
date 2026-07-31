# Context: DB Alembic Schema

## Target Folders

```
apps/api/app/infrastructure/
└── database.py              → SQLAlchemy ORM records (DeclarativeBase, Mapped, mapped_column)

apps/api/app/domain/
├── models.py                → StrEnum + @dataclass entities (source of truth for enums)
└── repositories.py          → Protocol interfaces (sync if new repo needed)

apps/api/alembic/
├── env.py                   → Alembic environment config
└── versions/                → Migration files: {date}_{nn}_{slug}.py
```

## Full ORM Record Pattern

```python
# infrastructure/database.py
from sqlalchemy import DateTime, Enum, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="UserRole"), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column("deleted_at", DateTime(timezone=False), nullable=True)
```

## Relation Pattern

```python
class BusinessShipmentRecord(Base):
    __tablename__ = "business_shipments"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column("user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    service_type_id: Mapped[str] = mapped_column("service_type_id", Uuid(as_uuid=False), ForeignKey("master_service_types.id"), nullable=False)

    user: Mapped["UserRecord"] = relationship(back_populates="shipments")
    service_type: Mapped["MasterServiceTypeRecord"] = relationship(back_populates="shipments")

    __table_args__ = (Index("ix_business_shipments_user_id", "user_id"),)
```

## Migration File Naming

```
alembic/versions/
├── 20260729_01_baseline_auth_schema.py
├── 20260801_01_tenant_foundation.py
└── {YYYYMMDD}_{NN}_{slug}.py
```

## Commands

```bash
uv run alembic revision --autogenerate -m "<description>"    # create migration
uv run alembic upgrade head                                    # apply migrations
uv run alembic downgrade -1                                    # rollback one migration (local only)
uv run alembic history                                         # view migration history
uv run alembic stamp <revision>                                # mark a revision as applied without running it
```
