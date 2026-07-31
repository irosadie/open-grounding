# Checklist: ops-docker

## Preparation

- [ ] Identify target: `apps/api` (Python) and/or `apps/worker` (Bun)
- [ ] Check ports exposed in source code

## Dockerfile (API — Python + uv)

- [ ] Multi-stage build (builder + runner)
- [ ] Base image: `python:3.12-slim`
- [ ] `uv` installed from `ghcr.io/astral-sh/uv:latest`
- [ ] `uv sync --frozen --no-dev` in builder stage
- [ ] `.venv` copied from builder to runner
- [ ] `alembic` migrations copied to runner
- [ ] `PATH` includes `.venv/bin`
- [ ] Non-root user created and used in runner stage
- [ ] `EXPOSE 3001`
- [ ] `CMD ["uvicorn", "app.main:app", ...]`

## Dockerfile (Worker — Bun + TypeScript)

- [ ] Base image: `oven/bun:1-alpine`
- [ ] `--frozen-lockfile` on `bun install`
- [ ] Monorepo packages (`packages/`) copied in builder stage
- [ ] Build artifact copied from builder to runner
- [ ] Non-root user created and used in runner stage
- [ ] `ENV NODE_ENV=production` in runner stage

## Security

- [ ] No `.env` or credentials in image
- [ ] Non-root user
- [ ] No dev dependencies in runner stage

## Validation

- [ ] Build succeeds: `docker build -f apps/{app}/Dockerfile -t test:latest .`
- [ ] Container runs: `docker run --rm -e ... test:latest`
- [ ] Reasonable image size

## Finalization

- [ ] Dockerfile ends with newline (EOF)
- [ ] `.dockerignore` exists at root if not present
- [ ] **Do NOT modify `docker-compose.yml`**
