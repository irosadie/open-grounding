# Agent Rules
You are a **principal engineer** in this monorepo. Follow all rules defined here.

## AI Tools Available

This project uses the following AI-powered tools:

- **Serena** — Advanced code navigation and symbol manipulation (find symbols, replace content, rename, refactor, diagnostics, and memory system)
- **Graphify** — Persistent codebase knowledge graph for architecture, relationship, and impact analysis
- **Headroom** — Context compression for large outputs (compress/retrieve/stats to save token usage)
- **RTK (Reading Toolkit)** — Enhanced file reading utilities installed globally
- **OpenSpec** — Structured workflow for feature development (propose → implement → verify → archive). Changes are tracked in `openspec/changes/`, with main specs in `openspec/specs/`

You have access to these tools' functions. Use them when appropriate for better performance and precision.

## Mandatory Skill and Tool Discipline

- **Skills and guardrails are authoritative.** Before acting, identify the matching skill and follow its workflow, references, checklist, folder contracts, and prohibitions. Do not substitute an unapproved pattern, architecture, or method based on assumptions or personal preference.
- **Do not hallucinate.** If the required skill, guardrail, tool, or project convention does not provide a clear answer, inspect the source of truth or ask the user. Never claim a tool result, project pattern, or implementation detail without verifying it.
- **Check Serena and Graphify before every task.** Confirm Serena is available for semantic code navigation, refactoring, and diagnostics. Confirm Graphify is available and whether a `.graphify/` knowledge graph exists or must be created.
- **Use the appropriate tool.** Use Serena for symbol-aware exploration and safe code changes. Use Graphify for codebase architecture, file relationships, dependency/impact analysis, and broad repository questions. If either tool is unavailable, state that limitation rather than silently replacing it with an invented workflow.

## Monorepo Structure

```
vibecoding-starter/
├── apps/
│   ├── web/      → Next.js frontend (App Router)
│   ├── api/      → FastAPI backend (Clean Architecture)
│   └── worker/   → BullMQ background worker
└── packages/
    ├── schemas/  → Zod validation schemas (shared FE + BE)
    ├── types/    → API response types (shared FE + BE)
    └── utils/    → Pure utility functions (shared all)
```

## `.agents` Structure (Must Stay Consistent)

```
.agents/
├── AGENTS.md
├── settings.json
├── guides/                  ← writing guides per topic (flat)
│   ├── ARCHITECTURE.md      ← layer map + all folder contracts (read first!)
│   ├── web-page.md
│   ├── web-component.md
│   ├── web-hook.md
│   ├── web-service.md
│   ├── web-type.md
│   ├── web-config.md
│   ├── web-constant.md
│   ├── web-provider.md
│   ├── web-util.md
│   ├── web-test.md
│   ├── api-entity.md
│   ├── api-usecase.md
│   ├── api-repository.md
│   ├── api-controller.md
│   ├── api-route.md
│   ├── api-service.md
│   ├── api-dto.md
│   ├── api-validator.md
│   ├── api-error.md
│   ├── api-db-repository.md
│   └── shared-schema.md
├── examples/                ← real code examples per scope
│   ├── web-slicing/
│   │   └── nextjs-app-router/
│   │       └── examples/     ← basic CRUD template
│   └── web-api-integrated/
│       └── hooks/
│           └── use-examples/ ← complete hook folder example
├── scripts/                 ← helper scripts for agent asset maintenance
│   ├── create-skill.mjs
│   ├── skill-utils.mjs
│   ├── sync-skill-registry.mjs
│   ├── sync-claude-skills.mjs
│   └── validate-skills.mjs
└── skills/
    ├── manifest.json
    └── <scope>-<capability>/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/context.md
        └── templates/checklist.md
```

## OpenAI + Claude Compatibility

- Source of truth for skills is `.agents/skills/*` with `SKILL.md` as the main definition.
- OpenAI/Codex entrypoint is root `AGENTS.md` (bridges to `.agents/AGENTS.md`).
- Claude entrypoint is root `CLAUDE.md`.
- Codex/OpenAI metadata lives in `agents/openai.yaml` with `interface` / `policy` / `dependencies` schema when needed.
- Claude skill wrappers live in `.claude/skills/*` and must be synced from source of truth.
- Registry table and skill reference lists are generated from `manifest.json` via `bun run skills:sync-registry`.
- After adding/renaming/editing skill metadata, run: `bun run skills:sync`
- Before merging skill asset changes, run: `bun run skills:validate`

## Skill Registry

<!-- skill-registry:start -->
| Skill | Scope | When to Use |
|---|---|---|
| `web-api-integrated` | Frontend | Integrate API endpoint to frontend with schema, types, constants, and hooks |
| `web-bugfix` | Frontend | Fix frontend bug with minimal touch and sync impacted contracts |
| `web-code-review` | Frontend | Review frontend code strictly before merge or during quality audit |
| `web-seo-geo-friendly` | Frontend | SEO and GEO optimization for public Next.js pages |
| `web-slicing` | Frontend | Implement UI from design, screenshot, or Figma |
| `api-bugfix` | Backend | Fix backend bug with minimal touch and sync impacted contracts |
| `api-code-review` | Backend | Review backend code strictly before merge or during quality audit |
| `api-feature` | Backend | Implement new backend feature following Clean Architecture |
| `db-alembic-schema` | Backend | Update SQLAlchemy ORM models and Alembic migrations |
| `docs-openapi` | Docs | Manage OpenAPI quality via FastAPI annotations and export spec |
| `ops-docker` | Ops | Write or modify backend Dockerfile for Linux deployment |
| `ops-mcp-setup` | Ops | Setup GitHub MCP for this repo's workflow |
| `flow-session-start` | Flow | Handle Start/Mulai command for repo onboarding |
| `meta-skill-hygiene` | Meta | Audit and maintain skill metadata consistency |
| `skill-add-example` | Meta | Add reusable example code for other skills |
| `skill-creator` | Meta | Create or update skills with consistent format |
| `openspec-apply-change` | OpenSpec | Implement tasks from an active OpenSpec change |
| `openspec-archive-change` | OpenSpec | Archive a completed OpenSpec change |
| `openspec-explore` | OpenSpec | Explore and think through ideas before committing to a change |
| `openspec-propose` | OpenSpec | Start a new feature — turn an idea into proposal + specs + design + tasks |
| `openspec-sync-specs` | OpenSpec | Sync delta specs to main specs |
<!-- skill-registry:end -->

## Core Principles

- **Minimal code** — write as little code as possible to complete the task. Don't over-engineer.
- **Precision over speed** — be fast, but results must be correct and match requirements.
- **Don't assume** — if something is ambiguous or unclear, ask first. Don't silently pick.
- **Suggest simpler alternatives** — push back if warranted.
- **Best practices required** — always apply current best practices for every technology used (Next.js App Router, FastAPI, SQLAlchemy async, Alembic, BullMQ, React Query, Zod, etc.).
- **Search the web if unsure** — if you're not certain about the best approach or want to verify the latest version/API, **search the web first**. Don't guess, don't use old patterns when better ones exist.
- **Follow the established flow** — don't skip phases. The vibe coding flow has an order: propose → implement → verify. Each phase has its skill, follow it.

## OpenSpec Requirement

**All code changes MUST go through the OpenSpec workflow.**

Why:
- **Structured thinking** — forces upfront design before implementation, reducing rework
- **Traceability** — every feature has proposal, specs, design, and tasks documented in `openspec/changes/`
- **Quality assurance** — changes are reviewed against specs before archiving
- **Context preservation** — future agents/developers can understand why decisions were made
- **Collaboration** — clear handoff between propose → implement → verify phases

Exceptions (direct implementation allowed):
- Trivial fixes (typos, formatting, dead code removal)
- Maintenance tasks (dependency updates, config adjustments)
- Documentation-only changes
- Emergency hotfixes (must be documented retroactively)

For feature work, bug fixes with business logic impact, or refactoring: **always start with `/opsx:propose`**.

## Start Session Protocol

If the user only types:
- `Start`
- `Mulai`
- `Mulai Vibe Coding`
- or similar start session variants

then **MUST** treat it as an onboarding session, not a direct implementation task.

Required steps:
1. Read `.agents/settings.json`
2. Run `bun run session:status`
3. Summarize MCP status, branch, and worktree
4. Classify session state:
   - possible first init
   - possible resume of last task
   - ready for new work item
5. Ask **one** clear next-step question

Default next step priority:
1. MCP not ready → direct to `ops-mcp-setup`
2. Active branch/task exists → offer to resume last task
3. Repo ready and user wants to start fresh → direct to OpenSpec `/opsx:propose`

## Vibe Coding Flow

> **MUST follow this order. Don't skip phases.**

### Phase 1 — Propose (OpenSpec)
Use `/opsx:propose` to turn a feature idea into proposal + specs + design + tasks.
```
Output: openspec/changes/{slug}/
          proposal.md
          specs/
          design.md
          tasks.md
```

### Phase 2 — Implementation (per task from OpenSpec)

Execution order per feature — **don't reverse**:

#### 2a. FE Slicing
> Skill: `web-slicing`
- UI from design/description, use dummy data first
- Target: `apps/web/app/(group)/[feature]/`
- Output: `page.tsx` + `[feature]-content.tsx`

#### 2b. Backend + OpenAPI
> Skill: `api-feature` + `docs-openapi`
- Implement Clean Architecture: entity → use case → repository → service → router
- Generate OpenAPI from FastAPI routers and Pydantic models
- Target: `apps/api/app/` + `docs/openapi.json`

#### 2c. FE ↔ API Integration
> Skill: `web-api-integrated`
- Zod schema, response types, constants, react-query hooks
- Wire the sliced UI to the running API
- Target: `packages/schemas/` + `packages/types/` + `apps/web/hooks/transactions/use-{domain}/` + `apps/web/constants/`

### Phase 3 — Verify & Archive
Use `/opsx:verify` for validation, then `/opsx:archive` for archiving.

### Phase 4 — Unit Test, Build & PR
Run before creating PR:
```bash
cd apps/web && bun run test
cd apps/api && bun run test
bun run build
```

After all pass:
1. Create PR
2. PR body: link to issue + implementation checklist

## Coding Guidelines

### Biome (Linter & Formatter) — MUST FOLLOW
> **Always read `biome.json` at root before writing code.**

Active rules that must be followed:
- **`noExplicitAny`: error** — `any` is forbidden. Always provide explicit types.
- **`noConsole`: error** — `console.log/warn/error` is forbidden. Use a proper logger or remove.
- **`useConst`: error** — use `const` if variable is not reassigned.
- **`noUnusedVariables`: error** — remove unused variables.
- **`noUnusedImports`: error** — remove unused imports.
- **Formatter:** indent `space` width 2, quote `"double"`, semicolons `asNeeded` (no semicolons at end of JS/TS lines).

Before submitting, ensure your code passes all rules above. If not, fix first.

### Enums — MUST be Shared from `packages/schemas/`
If a field/value has a fixed set of values, **MUST** declare as a shared enum. Values always `SCREAMING_SNAKE_CASE`. Source of truth is `packages/schemas/`:

```typescript
// packages/schemas/status.ts
export const statuses = ['ACTIVE', 'INACTIVE', 'ON_PROGRESS'] as const
export type Status = (typeof statuses)[number]
```

- **SQLAlchemy**: map persisted enum values explicitly and keep them compatible with the shared schema contract
- **BE entity/DTO**: define Python enum/model types within the FastAPI domain boundary
- **FE schema/form**: import `as const` array + `z.enum()` from `@vibecoding-starter/schemas`

One declaration, one import, all layers use the same.

### Simplicity First
- No features beyond what's requested.
- No abstractions for code used only once.
- No error handling for impossible scenarios.
- If 200 lines can be 50, rewrite.
- Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Surgical Changes
- Only touch what must change. Clean up only the mess you made.
- Don't "improve" code, comments, or formatting outside the task scope.
- Don't refactor what isn't broken.
- Follow existing code style, even if you'd do it differently.
- If there's dead code not from your changes, mention it — don't delete.
- Remove imports/variables/functions that **your changes** made unused.
- **Test:** every changed line must trace directly to the user's request.

## Task Management

- **Create a task checklist** before starting work.
- **Check off each task** immediately after completion, don't batch.
- **Before considering done**, review the entire checklist — ensure all tasks are checked.
- **Goal-driven** — transform tasks into verifiable goals:
  - "Add validation" → write test for invalid input, then pass it
  - "Fix bug" → write test that reproduces, then pass it
  - "Refactor X" → ensure tests pass before and after

## Application Flow (MUST FOLLOW)

> Read `.agents/guides/ARCHITECTURE.md` for full layer map and folder contracts.

### apps/web (Next.js Frontend)

```
Rendering (UI Layer):
  apps/web/app/ (router)
    └→ page.tsx (thin Suspense wrapper)
        └→ *-page-content.tsx (Client Component — route orchestration: hooks, state, layout)
            └→ _components/ (private route components: form, table, dialog, drawer)
                └→ apps/web/components/ (reusable components: Button, Input, Table, Dialog, etc.)

Data Flow (data transactions):
  *-page-content.tsx
    └→ apps/web/hooks/transactions/use-{domain}/ (custom hooks)
        └→ react-query (useQuery / useMutation)
            └→ axios instance (services/axios/)
                └→ API Server

Validation (input):
  Form (useForm + react-hook-form)
    └→ packages/schemas/ (shared Zod schema)

Typing:
  API response → packages/types/
  Form payload → z.infer<schema> (packages/schemas/)
  General      → apps/web/types/generals/
```

**API boundary (required):** UI files under `apps/web/app/**` (except `app/api/**`) and `apps/web/components/**` must not import `axios` or call `fetch` directly. Route UI consumes transaction hooks from `apps/web/hooks/transactions/use-{domain}/`; only those hooks may issue browser API requests. BFF route handlers in `app/api/**` and server-side auth remain explicit exceptions.
**RECOMMENDED:** create a `_components/` folder for components used only by that route. Keep `*-page-content.tsx` beside `page.tsx` as the route orchestrator. Move components used by multiple routes to `apps/web/components/`.

### apps/api (FastAPI Backend — Clean Architecture)

```
HTTP Request
  → apps/api/app/interfaces/http/            (Pydantic validation, dependency injection, routers)
  → apps/api/app/application/                (orchestrate use case, transform domain models)
  → apps/api/app/domain/                     (business rules and repository protocols)
  → apps/api/app/infrastructure/             (SQLAlchemy async repositories)
  ↑
  bubbles up → FastAPI exception handlers → HTTP Response

Error Handling:
  DomainError → errorHandler middleware
    ├── NOT_FOUND    → 404
    ├── UNAUTHORIZED → 401
    ├── FORBIDDEN    → 403
    ├── CONFLICT     → 409
    ├── VALIDATION   → 422
    └── INTERNAL     → 500
```

**FORBIDDEN:** business logic in routers, SQLAlchemy/HTTP in application use cases, HTTP exceptions outside the HTTP interface.

### apps/worker (BullMQ Worker)

```
BullMQ Worker scaffold
  → apps/worker/src/infrastructure/queue/ (worker registration)
  → apps/worker/src/application/use-cases/ (runtime summary / job orchestration)
  → feature-specific queues added when actually needed
```

### packages/ (Shared)

```
packages/schemas/  → Zod schemas (used by web + worker)
packages/types/    → API response types (used by web)
packages/utils/    → Pure TS utilities (used by web + worker)
```

**Shared packages rules:**
- `packages/schemas/` → only Zod schema + inferred types + shared constants
- `packages/types/` → only TypeScript types for API responses
- `packages/utils/` → only pure functions without FE/BE-specific dependencies

## Settings

**MUST read `.agents/settings.json` at the start of every task** to get project-specific config:
- Repo (owner, name)
- Branch format & examples
- Stack (frontend, backend, package manager)
- Important paths (guides, examples, skills)
- Required MCP

## References

### SETTINGS (Must Read at Start)
- Project config: `.agents/settings.json`
- Skill scope registry: `.agents/skills/manifest.json`

### ARCHITECTURE (Must Read for Implementation Tasks)
- Layer map + folder contracts: `.agents/guides/ARCHITECTURE.md`

### SKILL (Read Only When Needed)
- After selecting a skill, **must also read**:
  - `references/context.md` (scope folders + code examples)
  - `templates/checklist.md` (required step checklist)
<!-- skill-links:start -->
- For skill `web-api-integrated`: `.agents/skills/web-api-integrated/SKILL.md`
- For skill `web-bugfix`: `.agents/skills/web-bugfix/SKILL.md`
- For skill `web-code-review`: `.agents/skills/web-code-review/SKILL.md`
- For skill `web-seo-geo-friendly`: `.agents/skills/web-seo-geo-friendly/SKILL.md`
- For skill `web-slicing`: `.agents/skills/web-slicing/SKILL.md`
- For skill `api-bugfix`: `.agents/skills/api-bugfix/SKILL.md`
- For skill `api-code-review`: `.agents/skills/api-code-review/SKILL.md`
- For skill `api-feature`: `.agents/skills/api-feature/SKILL.md`
- For skill `db-alembic-schema`: `.agents/skills/db-alembic-schema/SKILL.md`
- For skill `docs-openapi`: `.agents/skills/docs-openapi/SKILL.md`
- For skill `ops-docker`: `.agents/skills/ops-docker/SKILL.md`
- For skill `ops-mcp-setup`: `.agents/skills/ops-mcp-setup/SKILL.md`
- For skill `flow-session-start`: `.agents/skills/flow-session-start/SKILL.md`
- For skill `meta-skill-hygiene`: `.agents/skills/meta-skill-hygiene/SKILL.md`
- For skill `skill-add-example`: `.agents/skills/skill-add-example/SKILL.md`
- For skill `skill-creator`: `.agents/skills/skill-creator/SKILL.md`
- For skill `openspec-apply-change`: `.agents/skills/openspec-apply-change/SKILL.md`
- For skill `openspec-archive-change`: `.agents/skills/openspec-archive-change/SKILL.md`
- For skill `openspec-explore`: `.agents/skills/openspec-explore/SKILL.md`
- For skill `openspec-propose`: `.agents/skills/openspec-propose/SKILL.md`
- For skill `openspec-sync-specs`: `.agents/skills/openspec-sync-specs/SKILL.md`
<!-- skill-links:end -->

### GUIDE (Read Only When Needed — when writing code in that folder)

**apps/web:**
- Page: `.agents/guides/web-page.md`
- Component: `.agents/guides/web-component.md`
- Hook: `.agents/guides/web-hook.md`
- Service: `.agents/guides/web-service.md`
- Type: `.agents/guides/web-type.md`
- Config: `.agents/guides/web-config.md`
- Constant: `.agents/guides/web-constant.md`
- Provider: `.agents/guides/web-provider.md`
- Util: `.agents/guides/web-util.md`
- Test setup: `.agents/guides/web-test.md`

**apps/api:**
- Entity: `.agents/guides/api-entity.md`
- Use Case: `.agents/guides/api-usecase.md`
- Repository Interface: `.agents/guides/api-repository.md`
- Controller: `.agents/guides/api-controller.md`
- Route: `.agents/guides/api-route.md`
- Service: `.agents/guides/api-service.md`
- DTO: `.agents/guides/api-dto.md`
- Validator: `.agents/guides/api-validator.md`
- Error: `.agents/guides/api-error.md`
- SQLAlchemy Repository: `.agents/guides/api-db-repository.md`

**packages:**
- Shared schema: `.agents/guides/shared-schema.md`
