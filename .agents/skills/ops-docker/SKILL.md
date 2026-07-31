---
name: ops-docker
description: Write or modify Dockerfiles for this backend so it is ready to deploy on Linux. Use for tasks involving containerization, image optimization, or build/runtime issues in containers. Docker Compose is managed by the server — do not touch it.
---

# Skill: Ops Docker

## Context (Required)
- Target: Dockerfile in `apps/api/` (Python/FastAPI) and/or `apps/worker/` (Bun/BullMQ)
- **Do NOT touch `docker-compose.yml`** — managed by the server

## Principles

- Multi-stage build to minimize image size
- `builder` stage: install deps + compile
- `runner` stage: runtime artifact only
- API: use `python:3.12-slim` + `uv` as runtime
- Worker: use `oven/bun:1-alpine` as runtime
- Run as non-root user

## Workflow

1. Identify target app and its runtime needs (Python API or Bun worker).
2. Copy required monorepo dependencies in the builder stage.
3. Build target artifact in `builder` stage.
4. Copy minimal artifact into `runner` stage.
5. Verify `CMD`, port, and runtime requirements before finishing.

## Dockerfile Template (FastAPI API — Python + uv)

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy API source and lock file
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./

# Compile bytecode
RUN uv run python -m compileall -q app

# Stage 2: Runner
FROM python:3.12-slim AS runner
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser

# Copy virtual environment and source
COPY --from=builder --chown=appuser:appgroup /app/.venv ./.venv
COPY --from=builder --chown=appuser:appgroup /app/app ./app
COPY --from=builder --chown=appuser:appgroup /app/alembic ./alembic
COPY --from=builder --chown=appuser:appgroup /app/alembic.ini ./
COPY --from=builder --chown=appuser:appgroup /app/pyproject.toml ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
```

## Dockerfile Template (BullMQ Worker — Bun + TypeScript)

```dockerfile
FROM oven/bun:1-alpine AS builder
WORKDIR /app

COPY package.json bun.lockb ./
COPY packages/ ./packages/
RUN bun install --frozen-lockfile

COPY apps/worker/ ./apps/worker/
RUN cd apps/worker && bun run build

FROM oven/bun:1-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

COPY --from=builder --chown=appuser:appgroup /app/apps/worker/dist ./dist
COPY --from=builder --chown=appuser:appgroup /app/apps/worker/package.json ./

CMD ["bun", "run", "dist/index.js"]
```

## Rules

- API: use `python:3.12-slim` base image + `uv` for dependency management
- Worker: use `oven/bun:1-alpine` base image + `bun install --frozen-lockfile`
- Never copy `.env` into the image — inject via environment variable at runtime
- Never expose unused ports
- API: ensure `alembic` migrations are available in the runner stage

## Prohibitions

- **FORBIDDEN** to modify `docker-compose.yml`.
- **FORBIDDEN** to run container as root unless strictly required.
- **FORBIDDEN** to copy the entire repo into the runner stage when only some artifacts are needed.
- **FORBIDDEN** to leave a Dockerfile that cannot be built deterministically.

## Pre-Completion Checklist

- [ ] Dockerfile uses multi-stage build
- [ ] Runner stage contains only minimal runtime artifact
- [ ] Non-root user is used
- [ ] Port and runtime command match target app
- [ ] API: `uv sync --frozen` used in builder, `.venv` copied to runner
- [ ] Worker: `bun install --frozen-lockfile` used in builder
- [ ] Container build verified or reason documented
- [ ] All files end with newline (EOF)
