# Context: API Feature

## Target Folders

```
apps/api/app/
├── domain/
│   ├── models.py              → entity (@dataclass) + StrEnum
│   ├── repositories.py        → Protocol interface
│   ├── errors.py              → DomainError + classmethod factories
│   └── use_cases/             → {verb}_{domain}.py (one per operation)
├── application/
│   ├── {domain}_service.py    → {Domain}Service class
│   └── dtos.py                → Pydantic response models
├── infrastructure/
│   └── database.py            → ORM records + SqlAlchemy repos + _to_* mappers
├── interfaces/http/
│   ├── routes.py              → APIRouter handlers (controller = inline)
│   ├── schemas.py             → Pydantic request models
│   └── dependencies.py       → Depends providers + Annotated aliases
└── main.py                    → create_app() + router registration
```

## Pattern per Layer

### Entity
```python
@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime
```

### Repository Protocol
```python
class UserRepository(Protocol):
    async def find_by_id(self, user_id: str) -> User | None: ...
    async def create(self, *, email: str, name: str) -> User: ...
```

### Use Case
```python
async def register_user(repo: UserRepository, *, email: str, name: str) -> User:
    existing = await repo.find_by_email(email)
    if existing:
        raise DomainError.duplicate_email()
    return await repo.create(email=email, name=name)
```

### Service
```python
class AuthService:
    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    async def register(self, *, name: str, email: str, password: str) -> dict[str, object]:
        user = await register_user(self._repository, email=email, password_hash=hash_password(password), name=name)
        return {"user": _user_dto(user)}
```

### Route Handler (Controller)
```python
@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success("Register success", await service.register(name=payload.name, email=str(payload.email), password=payload.password))
```
