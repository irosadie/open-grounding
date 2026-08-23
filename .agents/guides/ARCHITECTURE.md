# Architecture: Layer Map + Folder Contracts

Read this file at the start of each implementation session. Contains complete layer map and contracts per folder.

---

## Monorepo Overview

```
open-grounding/
├── apps/
│   ├── web/      → Next.js 16 App Router (frontend)
│   ├── api/      → FastAPI (backend, Clean Architecture, Python)
│   └── worker/   → BullMQ (background job processor)
└── packages/
    ├── schemas/  → Zod validation schemas (shared FE + Worker)
    ├── types/    → API response TypeScript types (shared FE)
    └── utils/    → Pure utility functions (shared FE + Worker)
```

---

## apps/web — Next.js App Router

### Layer Map

```
apps/web/
├── app/                    → Router: pages, layouts, route groups, route handlers
│   └── (group)/
│       └── feature/
│           ├── page.tsx                 → Server Component (thin Suspense wrapper)
│           ├── feature-page-content.tsx → Client Component (route orchestration)
│           └── _components/             → Private components for this route
├── auth.ts                 → NextAuth credentials config (server-only)
├── proxy.ts                → Route protection / redirect logic in edge layer
├── components/             → Reusable UI components (used >1 page)
├── hooks/
│   ├── transactions/       → Data-fetching hooks per domain
│   │   └── use-{domain}/   → One folder per domain
│   │       ├── use-data-table.ts
│   │       ├── use-get-one.ts
│   │       ├── use-insert-one.ts
│   │       ├── use-update-one.ts
│   │       ├── use-delete-one.ts
│   │       └── index.ts
│   └── utility/            → Non-data hooks (useQueryParam, etc.)
├── services/
│   └── axios/              → Axios instance with interceptors
├── constants/
│   ├── api-routers.ts      → All API URL constants (use :id path variable)
│   └── query-keys.ts       → All react-query cache key constants (flat strings)
├── types/generals/         → FE-specific types not from API
├── configs/                → App-wide config (env, auth, etc.)
├── providers/              → React context providers
└── utils/                  → FE-specific helper functions (debounce, pathVariable, etc.)
```

### Data Flow

```
page.tsx (Server Component — thin Suspense wrapper)
  └→ feature-page-content.tsx (Client Component — route state, hooks, layout)
      ├→ _components/ (private form, table, dialog, drawer)
      └→ Custom Hook (hooks/transactions/use-{domain}/)
          └→ react-query useQuery / useMutation
              └→ axios instance (services/axios/)
                  └→ app/api/proxy/[...path]/route.ts
                      └→ API Server
```

### Contracts per Folder

#### `app/` — Pages & Layouts

✅ Allowed:
- `page.tsx` contains only Suspense wrapper + import content component
- Import `LoadingSpinner` or skeleton component for Suspense fallback
- Export `generateMetadata`, `generateStaticParams`
- Thin route handler for auth or proxy allowed under `app/api/`

❌ Forbidden:
- Call `axios` or `fetch` directly
- Import from `services/` directly
- Business logic or state management
- Place reusable cross-route components in `_components/` — use `apps/web/components/` instead

---

#### `app/api/(auth)/auth/[...nextauth]/route.ts` — NextAuth Route Handler

✅ Allowed:
- Wrap `NextAuth(authOptions)` and export handler `GET`/`POST`
- Stay thin and only be App Router entrypoint for auth

❌ Forbidden:
- Put login business logic directly in route handler
- Call backend auth directly here if logic already exists in `auth.ts`

---

#### `app/api/proxy/[...path]/route.ts` — Internal BFF Proxy

✅ Allowed:
- Forward browser request to backend API
- Add bearer token from NextAuth session
- Refresh access token and update session cookie when needed
- Pass public auth endpoints like login/refresh without bearer token

❌ Forbidden:
- Put feature business logic
- Add domain-specific response transformation at this route level
- Make this route a stateful cache or business orchestration point

---

#### `proxy.ts` — Edge Route Protection

✅ Allowed:
- Redirect guest to login page for protected routes
- Redirect logged-in user from `/login` to default page
- Read cookie/session token for lightweight guard
- Read config from `auth.ts` and `configs/auth-server.ts`

❌ Forbidden:
- Application business logic
- Fetch business data or call internal API to render page
- Put main auth config here — keep it in `auth.ts`

---

#### `*-page-content.tsx` — Main Client Component

✅ Allowed:
- All `useState`, `useEffect`, hooks
- Import and call hooks from `hooks/`
- Define `columns` array for table
- Form handling with react-hook-form
- Dialog state and logic
- Query params via `useQueryParam`
- Delete confirmation via SweetAlert2

❌ Forbidden:
- Call `axios` or `fetch` directly
- Import from `services/` directly

---

#### `_components/` — Private Route Components

✅ Allowed:
- Presentational or focused components used only by the current route
- Route-specific toolbar, table, form dialog, drawer, and loading components

❌ Forbidden:
- Reuse from another route — move cross-route components to `apps/web/components/`
- Direct `axios` or `fetch` calls

---

#### `components/` — Reusable UI Components

✅ Allowed:
- Accept props, render JSX
- Import UI library components (Button, Input, Dialog, Table, etc.)
- `useState`, `useEffect` for local UI state

❌ Forbidden:
- Call `axios` or `fetch` directly
- Import data-fetching hooks from `hooks/`
- Hardcode API URL or query key

---

#### `hooks/transactions/use-{domain}/` — Custom React Hooks

✅ Allowed:
- Wrap `useQuery`, `useMutation` from react-query
- Call `axios` instance directly (no need for separate service function)
- Use `queryKeys` and `apiRouters` from `constants/`
- `useDataTable` = react-query `useQuery` to fetch paginated list data

❌ Forbidden:
- Contains JSX
- One hook for all operations — separate per file
- Hardcode URL — use `apiRouters` from constants

---

#### `hooks/utility/` — Utility Hooks

✅ Allowed:
- `useQueryParam` — wrap `useSearchParams` + `useRouter` + `usePathname`

❌ Forbidden:
- Contains data-fetching or business logic

---

#### `services/axios/` — Axios Instance

✅ Allowed:
- Setup axios instance with internal proxy base URL from `configs/env.ts`
- Response interceptor to unwrap data and lightweight `401` redirect to login
- Response interceptor unwrap `{ meta, data }` → `DataTableResponse` for list

❌ Forbidden:
- Service function per endpoint — that goes directly in hook
- Business logic
- Inject bearer token browser-side if request goes through internal proxy

---

#### `constants/` — Application Constants

✅ Allowed:
- `api-routers.ts`: flat object with `:id` path variables (e.g. `/users/:id`)
- `query-keys.ts`: flat string values per operation (e.g. `index: 'usersIndex'`)

❌ Forbidden:
- Business logic
- Function for path variable — use `pathVariable()` utility
- Values from env (use `configs/`)

---

#### `packages/schemas/` — Zod Schemas (Shared)

✅ Allowed:
- Type constants array + labels array + `get{Type}Label()` helper
- Zod schema for form payload
- Export `type Props = z.infer<typeof schema>`

❌ Forbidden:
- Import FE or BE-specific library
- Business logic or API call

---

#### `packages/types/` — API Response Types (Shared)

✅ Allowed:
- TypeScript `type` for API response
- Re-export from `index.ts`

❌ Forbidden:
- Use `any`
- Request/payload types (use `packages/schemas/`)

---

## apps/api — FastAPI Backend (Clean Architecture)

### Layer Map

```
apps/api/app/
│   ├── interfaces/http/
│   │   ├── routes.py            → APIRouter handlers (controller = inline)
│   │   ├── schemas.py           → Pydantic request models (validation)
│   │   ├── dependencies.py     → FastAPI Depends DI + Annotated aliases
│   │   └── errors.py            → Exception handlers (DomainError, ValidationError)
│   ├── application/
│   │   ├── {domain}_service.py  → Orchestrate use cases, Entity → DTO
│   │   └── dtos.py             → Pydantic response models (output shapes)
│   ├── domain/
│   │   ├── models.py            → Domain entities (@dataclass) + StrEnum
│   │   ├── repositories.py     → Repository interfaces (Protocol)
│   │   ├── errors.py            → DomainError + classmethod factories
│   │   └── use_cases/           → Business logic (one file per operation)
│   ├── infrastructure/
│   │   └── database.py          → SQLAlchemy ORM records + repository impls + _to_* mappers
└── core/
    ├── settings.py          → Pydantic-settings BaseSettings
    └── security.py          → JWT, password hash
```

### Request Lifecycle (Hybrid 4-Hop)

```
HTTP Request
  → routes.py        (Pydantic validation, delegate to service — handler IS controller)
  → service          (orchestrate use cases, Entity → DTO)
  → use_cases/       (business logic, raise DomainError)
  → repositories     (Protocol contract)
  → database.py      (SQLAlchemy implementation, return Entity)
  ↑
  DomainError → @app.exception_handler(DomainError) → JSON Response
```

### Error Handling

```
DomainError → @app.exception_handler(DomainError)
  ├── NOT_FOUND          → 404
  ├── UNAUTHORIZED       → 401
  ├── FORBIDDEN          → 403
  ├── CONFLICT           → 409
  ├── VALIDATION_ERROR   → 422 (RequestValidationError)
  └── INTERNAL_SERVER_ERROR → 500
```

### Contracts per Layer

#### `interfaces/http/routes.py` — HTTP Routes (Controller = Inline)

✅ Allowed:
- Define `APIRouter` with prefix and tags
- Validate request with Pydantic model (auto-validated by FastAPI)
- Delegate to service method — handler IS the controller
- Attach dependencies per route via `Depends()`

❌ Forbidden:
- Business logic
- Call use case or repository directly — must go through service
- Format response manually (use `success()` envelope helper)

---

#### `application/{domain}_service.py` — Application Services

✅ Allowed:
- Orchestrate one or more use cases
- Transform Entity to DTO before returning to route handler
- Inject repository interface and settings via `__init__`

❌ Forbidden:
- Business logic — that's in use case
- Access SQLAlchemy directly — must go through repository interface
- HTTP concern (status code, header, JSONResponse)
- `try/except` for domain error — let it bubble

---

#### `domain/use_cases/` — Use Cases

✅ Allowed:
- Contains one business logic operation per file
- Raise `DomainError` for expected errors
- Call repository interface (Protocol)
- One file per operation: `register_user.py`, `get_user_by_id.py`

❌ Forbidden:
- Access SQLAlchemy or database directly
- HTTP concern (import from FastAPI)
- Raise `HTTPException` — use `DomainError`

---

#### `domain/models.py` — Domain Entities

✅ Allowed:
- `@dataclass(frozen=True)` that represents a domain model
- `StrEnum` for fixed-value fields
- Pure domain methods (without external dependency)

❌ Forbidden:
- Import SQLAlchemy types or ORM records
- HTTP or database dependency

---

#### `domain/repositories.py` — Repository Interfaces

✅ Allowed:
- Define `Protocol` class
- Method signature: `async def find_by_id(self, user_id: str) -> User | None`
- Use Entity types from `domain/models.py`

❌ Forbidden:
- Concrete implementation — that's in `infrastructure/database.py`
- Import SQLAlchemy
- Business logic

---

#### `infrastructure/database.py` — SQLAlchemy Repositories

✅ Allowed:
- Implement repository Protocol from `domain/repositories.py`
- Access SQLAlchemy `AsyncSession`
- Map ORM record to domain Entity via `_to_*` mapper

❌ Forbidden:
- Business logic
- Return raw ORM record — must map to Entity
- HTTP concern

---

#### `core/settings.py` — Runtime Config

✅ Allowed:
- Parse env with `pydantic-settings` BaseSettings
- Setup application config needed at runtime bootstrap

❌ Forbidden:
- Business logic
- Generic cross-app utility — move to `packages/*`
- Create `shared/` folder at app level for similar config

---

## apps/worker — BullMQ Worker

### Layer Map

```
apps/worker/src/
├── infrastructure/config/  → Runtime config (env, Redis config, etc.)
├── infrastructure/queue/   → Worker setup, consume BullMQ job
├── application/use-cases/  → Process job logic
└── domain/entities/        → Job entity types
```

### Job Flow

```
BullMQ Queue (job data defined in packages/schemas/)
  → infrastructure/queue/   (Worker setup, parse + validate job data)
  → application/use-cases/  (process job: send email, sync data, etc.)
  → domain/entities/        (job entity types)
```

### Worker Notes

- Don't create `shared/` folder at worker app level
- Shared across apps stays in `packages/*`
- Worker env goes into `apps/worker/src/infrastructure/config/`

---

## packages/ — Shared Packages

### Contracts

#### `packages/schemas/` — Zod Schemas

✅ Allowed:
- Zod schema for form payload, request body, job data
- `z.infer<>` types
- Shared enum/constant values

❌ Forbidden:
- FE-specific imports (React). The backend is Python and does not import this package.
- Business logic, side effects

---

#### `packages/types/` — API Response Types

✅ Allowed:
- TypeScript `type`/`interface` for API responses
- Re-export from `index.ts`

❌ Forbidden:
- `any`
- Zod dependency
- Request/payload types (use `packages/schemas/`)

---

#### `packages/utils/` — Pure Utilities

✅ Allowed:
- Pure functions without side effects
- Format, transform, parse helpers

❌ Forbidden:
- Import FE-specific (React) library. The backend is Python — do not import Hono, Prisma, or any BE library here.
- State management
- API calls
