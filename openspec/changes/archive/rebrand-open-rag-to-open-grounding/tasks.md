## 1. Package Names & Workspace Identifiers

- [x] 1.1 Update `package.json` root: `name` → `open-grounding`, turbo filter scripts
- [x] 1.2 Update `apps/web/package.json`: `name` → `@open-grounding/web`
- [x] 1.3 Update `apps/api/package.json`: `name` → `@open-grounding/api`
- [x] 1.4 Update `apps/worker/package.json`: `name` → `@open-grounding/worker`
- [x] 1.5 Update `packages/schemas/package.json`: `name` → `@open-grounding/schemas`
- [x] 1.6 Update `packages/types/package.json`: `name` → `@open-grounding/types`
- [x] 1.7 Update `packages/utils/package.json`: `name` → `@open-grounding/utils`

## 2. TypeScript Path Aliases

- [x] 2.1 Update `tsconfig.base.json` path aliases `@vibecoding-starter/*` → `@open-grounding/*`
- [x] 2.2 Update `apps/web/tsconfig.json` path aliases
- [x] 2.3 Update `apps/worker/tsconfig.json` path aliases (if exists)
- [x] 2.4 Update `.agents/examples/tsconfig.json` path aliases

## 3. Source File Imports

- [x] 3.1 Replace all `@vibecoding-starter/schemas` → `@open-grounding/schemas` in source files
- [x] 3.2 Replace all `@vibecoding-starter/types` → `@open-grounding/types` in source files
- [x] 3.3 Replace all `@vibecoding-starter/utils` → `@open-grounding/utils` in source files

## 4. Docker & Infrastructure

- [x] 4.1 Update `docker-compose.yml` container names → `open-grounding-*`
- [x] 4.2 Update `docker-compose.yml` DB name → `open_grounding`
- [x] 4.3 Update `apps/api/.env` DATABASE_URL → `open_grounding`
- [x] 4.4 Update `apps/api/.env.example` DATABASE_URL → `open_grounding`

## 5. API App Identity

- [x] 5.1 Update `apps/api` system route response: `name` field → `open-grounding-api`
- [x] 5.2 Update test assertion for app name in `tests/test_system_routes.py`

## 6. UI Brand Strings

- [x] 6.1 Update `apps/web/app/layout.tsx` metadata title → `open-grounding`
- [x] 6.2 Update `apps/web/components/console-topbar/console-topbar.tsx` → `Open Grounding Console`
- [x] 6.3 Update `apps/web/app/home-content.tsx` brand references
- [x] 6.4 Update `apps/web/app/console/settings/settings-content.tsx` platform name references

## 7. Docs & README

- [x] 7.1 Update `README.md` title and all `vibecoding-starter` references
- [x] 7.2 Update `docs/OPERATION.md` brand references
- [x] 7.3 Update `docs/RAG-CONSOLE-UI.md` → `Open Grounding Console`
- [x] 7.4 Update `docs/RAG-PLATFORM-OPERATIONS.md` → `Open Grounding Platform`
- [x] 7.5 Update `docs/RAG-ARCHITECTURE.md` brand references

## 8. Agent Config

- [x] 8.1 Update `.agents/settings.json` project name → `open-grounding`
- [x] 8.2 Update `.agents/AGENTS.md` monorepo name reference
- [x] 8.3 Update `.agents/guides/` import path examples `@vibecoding-starter/*` → `@open-grounding/*`
- [x] 8.4 Update `.agents/examples/` import path references

## 9. Lockfile & Verification

- [x] 9.1 Run `bun install` to regenerate `bun.lock` with new package names
- [x] 9.2 Run `bun run typecheck` (web) — no errors
- [x] 9.3 Run `bun run lint` (web) — no errors
- [x] 9.4 Run `bun run test` (web) — all pass
- [x] 9.5 Run `bun run test` (api) — all pass
