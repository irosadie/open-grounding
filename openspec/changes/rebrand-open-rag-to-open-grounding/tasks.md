## 1. Package Names & Workspace Identifiers

- [ ] 1.1 Update `package.json` root: `name` → `open-grounding`, turbo filter scripts
- [ ] 1.2 Update `apps/web/package.json`: `name` → `@open-grounding/web`
- [ ] 1.3 Update `apps/api/package.json`: `name` → `@open-grounding/api`
- [ ] 1.4 Update `apps/worker/package.json`: `name` → `@open-grounding/worker`
- [ ] 1.5 Update `packages/schemas/package.json`: `name` → `@open-grounding/schemas`
- [ ] 1.6 Update `packages/types/package.json`: `name` → `@open-grounding/types`
- [ ] 1.7 Update `packages/utils/package.json`: `name` → `@open-grounding/utils`

## 2. TypeScript Path Aliases

- [ ] 2.1 Update `tsconfig.base.json` path aliases `@vibecoding-starter/*` → `@open-grounding/*`
- [ ] 2.2 Update `apps/web/tsconfig.json` path aliases
- [ ] 2.3 Update `apps/worker/tsconfig.json` path aliases (if exists)
- [ ] 2.4 Update `.agents/examples/tsconfig.json` path aliases

## 3. Source File Imports

- [ ] 3.1 Replace all `@vibecoding-starter/schemas` → `@open-grounding/schemas` in source files
- [ ] 3.2 Replace all `@vibecoding-starter/types` → `@open-grounding/types` in source files
- [ ] 3.3 Replace all `@vibecoding-starter/utils` → `@open-grounding/utils` in source files

## 4. Docker & Infrastructure

- [ ] 4.1 Update `docker-compose.yml` container names → `open-grounding-*`
- [ ] 4.2 Update `docker-compose.yml` DB name → `open_grounding`
- [ ] 4.3 Update `apps/api/.env` DATABASE_URL → `open_grounding`
- [ ] 4.4 Update `apps/api/.env.example` DATABASE_URL → `open_grounding`

## 5. API App Identity

- [ ] 5.1 Update `apps/api` system route response: `name` field → `open-grounding-api`
- [ ] 5.2 Update test assertion for app name in `tests/test_system_routes.py`

## 6. UI Brand Strings

- [ ] 6.1 Update `apps/web/app/layout.tsx` metadata title → `open-grounding`
- [ ] 6.2 Update `apps/web/components/console-topbar/console-topbar.tsx` → `Open Grounding Console`
- [ ] 6.3 Update `apps/web/app/home-content.tsx` brand references
- [ ] 6.4 Update `apps/web/app/console/settings/settings-content.tsx` platform name references

## 7. Docs & README

- [ ] 7.1 Update `README.md` title and all `vibecoding-starter` references
- [ ] 7.2 Update `docs/OPERATION.md` brand references
- [ ] 7.3 Update `docs/RAG-CONSOLE-UI.md` → `Open Grounding Console`
- [ ] 7.4 Update `docs/RAG-PLATFORM-OPERATIONS.md` → `Open Grounding Platform`
- [ ] 7.5 Update `docs/RAG-ARCHITECTURE.md` brand references

## 8. Agent Config

- [ ] 8.1 Update `.agents/settings.json` project name → `open-grounding`
- [ ] 8.2 Update `.agents/AGENTS.md` monorepo name reference
- [ ] 8.3 Update `.agents/guides/` import path examples `@vibecoding-starter/*` → `@open-grounding/*`
- [ ] 8.4 Update `.agents/examples/` import path references

## 9. Lockfile & Verification

- [ ] 9.1 Run `bun install` to regenerate `bun.lock` with new package names
- [ ] 9.2 Run `bun run typecheck` (web) — no errors
- [ ] 9.3 Run `bun run lint` (web) — no errors
- [ ] 9.4 Run `bun run test` (web) — all pass
- [ ] 9.5 Run `bun run test` (api) — all pass
