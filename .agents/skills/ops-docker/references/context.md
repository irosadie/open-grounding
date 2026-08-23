# Context: ops-docker

## Target Files

```
apps/api/Dockerfile      → FastAPI API (Python + uv)
apps/worker/Dockerfile   → BullMQ Worker (Bun + TypeScript)
```

## Monorepo Structure in Container

```
/app/
├── package.json       ← monorepo root (for worker build)
├── bun.lockb
├── packages/          ← shared TS packages (for worker)
└── apps/
    ├── api/           → Python FastAPI service
    │   ├── app/
    │   ├── alembic/
    │   ├── pyproject.toml
    │   └── uv.lock
    └── worker/        → Bun BullMQ worker
```

## Python + uv in Docker (API)

The API uses `uv` for dependency management. In the builder stage:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev
```

Copy the virtual environment to the runner stage:

```dockerfile
COPY --from=builder /app/.venv ./.venv
ENV PATH="/app/.venv/bin:$PATH"
```

Alembic migrations must be available in the runner for `alembic upgrade head` at startup.

## Environment Variables

Never hardcode in Dockerfile. Inject at `docker run` or via orchestrator:

```bash
docker run \
  -e DATABASE_URL="postgresql://..." \
  -e JWT_SECRET="..." \
  -e DEPLOYMENT_TENANT_ID="..." \
  -e REDIS_URL="redis://..." \
  -p 3001:3001 \
  my-api:latest
```

## Build Command

```bash
# From monorepo root
docker build -f apps/api/Dockerfile -t my-api:latest .
docker build -f apps/worker/Dockerfile -t my-worker:latest .
```

Build context must be the root so `packages/` can be copied (for worker).

## Layer Caching Tips

Optimal COPY order for cache hits:
1. `pyproject.toml` + `uv.lock` (rarely change)
2. `uv sync --frozen` (cache keyed by lockfile)
3. Source code (changes often — place last)

## .dockerignore

```
node_modules
.env
.env.*
.venv
__pycache__
*.pyc
dist
.git
apps/web
docs
```
