# vibecoding-starter

Starter monorepo for building products with **vibe coding** — a workflow where AI agents (Claude Code / Codex) handle implementation tasks end-to-end, from feature planning to merge-ready PRs.

This repo provides two things:
1. **Production-ready starter monorepo** (Next.js + FastAPI + BullMQ + shared Docker PostgreSQL + Redis)
2. **Agent system** (`.agents/`) containing skills, guides, and code examples used by AI agents during coding

Status:
- Open source under [MIT](./LICENSE) license
- Clone, fork, use as a baseline for new projects, or contribute back via pull requests
- Agent workflow source of truth lives in `.agents/`

## Table of Contents

- [Open Source](#open-source)
- [What's Included](#whats-included)
- [Quick Start](#quick-start)
- [Key Endpoints](#key-endpoints)
- [OpenAPI & Scalar](#openapi--scalar)
- [Quality Checks](#quality-checks)
- [Start a Session](#start-a-session)
  - [Invoking Skills Explicitly](#invoking-skills-explicitly)
- [Vibe Coding Flow](#vibe-coding-flow)
- [Developing the Agent System](#developing-the-agent-system)
- [MCP Setup](#mcp-setup-for-ai-agents)
- [Contributing](#contributing)
- [License](#license)

Stack:
- `apps/web`: Next.js + Tailwind + Vitest
- `apps/api`: FastAPI (Clean Architecture) + SQLAlchemy async + Alembic + Pytest
- `apps/worker`: Worker scaffold + Redis + Vitest
- Shared service compose: PostgreSQL + Redis for local development
- `scripts/`: repo-level helper executables for bootstrap and operations
- `Turbo` for task orchestration
- `Bun` as package manager and script runner
- `Biome` for lint/format

## Open Source

This repo is intended for public use:
- Clone and use directly as a baseline for new projects
- Fork for internal or custom workflow versions
- Open issues or pull requests for fixes, cleanup, or new features
- Licensed under **MIT** — commercial and non-commercial use allowed as long as the license notice is preserved

## What's Included

### Monorepo Runtime
- `apps/web` — Next.js App Router frontend
- `apps/api` — FastAPI backend with clean architecture layering
- `apps/worker` — Redis-based background worker
- `/Users/binarydev/Program/General/service/docker-compose.yml` — shared PostgreSQL + Redis
- `scripts/bootstrap-local.sh`, `scripts/compose.sh`, and other repo-level helpers

### Frontend Starter
- App Router baseline pages
- `NextAuth` credentials-based auth foundation in `apps/web/auth.ts`
- Auth route handler at `apps/web/app/api/(auth)/auth/[...nextauth]/route.ts`
- Internal BFF proxy at `apps/web/app/api/proxy/[...path]/route.ts`
- Starter login page `/login` and register page `/register`
- Route protection and basic redirects via `apps/web/proxy.ts`
- `SessionProvider` and `QueryProvider`
- Query client service and axios interceptors defaulting to internal proxy `/api/proxy`
- Baseline constants for API routes and query keys
- Utility hooks: `useQueryParam`, `useNetworkInfo`, `useUserAgent`
- Utility helpers: `cn`, `objectToForm`, `rbacFilterMenu`
- General frontend types for App Router, data tables, and NextAuth augmentation
- Comprehensive reusable UI kit including:
  - action dropdown, autocomplete, avatar, breadcrumb
  - button, input, textarea, select, radio, radio-group, datepicker, file upload
  - currency input, currency select, currency display, content title
  - dialog, drawer, dropdown, menubar, tabs
  - table, pagination, status badge, stat card, panel card, panel context, search toolbar
  - text editor, map, route card, stepper, loading spinner, loading overlay, content loading, display with skeleton, empty state, user menu

### Backend Starter
- API entrypoint with `/` and `/health` endpoints
- Service + use case baseline for system info and health check
- Controller, route, and test baseline for system endpoints
- `DomainError` foundation for domain error handling
- Separate env config in `infrastructure/config`
- Middleware foundation for JWT, advanced auth, validation, and centralized error handling
- HTTP response/query parser utilities and OpenAPI merge helper
- Domain service skeleton for token and storage
- JWT / token blacklist foundation for future auth features
- Example use case test scaffold for backend patterns
- SQLAlchemy async persistence and Alembic migrations ready for development

### Worker Starter
- Worker entrypoint connected to Redis
- Summary use case for idle/active worker mode
- Separate env config in `infrastructure/config`
- Minimal queue bootstrap to start the first worker without business features

### Shared Packages
- `packages/schemas` — shared Zod schemas including auth/login starter
- `packages/types` — shared response types baseline (`success`, `error`, auth response starter)
- `packages/utils` — pure utility functions shared across apps

Utilities in `packages/utils`:
- currency format, date range, debounce, enum to object, string generator
- masking, number helpers, path variable, point converter, time helpers, to-camel-case

### Docs & DevEx
- OpenAPI generated from FastAPI at `docs/openapi.json`
- [Scalar](https://scalar.com/) config at `apps/api/scalar.config.json` pointing to the merged spec
- GitHub Actions for app CI and skill hygiene

### Agent Workflow
- Onboarding session via `bun run session:status`
- Planning & specs via [OpenSpec](https://github.com/Fission-AI/OpenSpec) (`/opsx:propose`)
- Skill registry and agent entrypoint in `.agents/AGENTS.md`
- Source of truth skills in `.agents/skills/`
- Reusable examples in `.agents/examples/`
- Claude wrappers auto-generated from source of truth skills

## Quick Start

Prerequisites:
- Bun `>= 1.3`
- Docker

```bash
bun install
bun run bootstrap
bun run dev
```

`bun run bootstrap` will:
- Copy `.env.example` to `.env` if it doesn't exist
- Start PostgreSQL and Redis
- Wait for services to be ready
- Apply the Alembic baseline migration
- Generate merged OpenAPI spec

After bootstrapping, initialize OpenSpec for the planning layer:

```bash
bunx openspec init
```

This sets up the `openspec/` directory and generates slash commands for your AI tool of choice:
- **Claude Code** — commands are added to `.claude/commands/`
- **Codex** — invoke skills with `$openspec-propose`, `$openspec-apply-change`, etc.
- **OpenCode** — instructions are loaded via `opencode.md` and `.opencode.json`

Daily commands:
```bash
bun run stack:up
bun run stack:down
bun run stack:logs
bun run session:status
bun run db:upgrade
bun run db:stamp-baseline
bun run openapi:generate
```

## Key Endpoints
- Web: `http://localhost:3000`
- Web login: `http://localhost:3000/login`
- Web register: `http://localhost:3000/register`
- Web auth route: `http://localhost:3000/api/auth/*`
- Web internal proxy: `http://localhost:3000/api/proxy/*`
- API root: `http://localhost:3001/`
- API health: `http://localhost:3001/health`
- Merged OpenAPI spec: `docs/openapi.json`
- Scalar config source: `apps/api/scalar.config.json`

## OpenAPI & Scalar

The OpenAPI workflow is ready for docs tooling:
- FastAPI routers and Pydantic models are the OpenAPI source of truth
- Generated artifact at `docs/openapi.json`
- Generator runs via `bun run openapi:generate`
- Scalar config at `apps/api/scalar.config.json`

This means:
- Don't edit `docs/openapi.json` directly
- Update FastAPI routers or Pydantic models
- Regenerate the merged spec afterward
- The merged file is ready for Scalar since the repo config points to `./docs/openapi.json`

## Quality Checks

```bash
bun run check
```

Partial commands:
```bash
bun run lint
bun run typecheck
bun run test
bun run build
```

Generate merged OpenAPI spec:
```bash
bun run openapi:generate
```

## Start a Session

Type **"Start"** or **"Mulai Vibe Coding"** in Claude Code or Codex.

The agent will run a quick check:
- Check repo-level MCP (`.mcp.json`) and missing services
- Check active branch and whether there's work in progress

Then it will direct the session to one of:
- Set up MCP first
- Resume last task
- Start a new feature via OpenSpec (`/opsx:propose`)

To run the same quick check manually:

```bash
bun run session:status
```

### Invoking Skills Explicitly

Skills can be invoked directly — use these if you want full control:

**Claude Code** — use `/` prefix:
```
/web-slicing
/api-feature
/web-api-integrated
```

**Codex** — use `$` prefix:
```
$web-slicing
$api-feature
$web-api-integrated
```

Full skill list available in `.agents/AGENTS.md` under `Skill Registry`.

---

## Developing the Agent System

### Creating a New Skill

Use the `skill-creator` skill to add new capabilities to the agent system.

**Claude:** `/skill-creator` &nbsp;|&nbsp; **Codex:** `$skill-creator`

Or run the generator directly:

```bash
bun run skills:create -- \
  --name {scope}-{capability} \
  --scope {scope} \
  --description "{One-line description}" \
  --when "{When to use}"
```

The generator creates the full structure:

```
.agents/skills/{name}/
├── SKILL.md                → Definition + workflow + constraints + checklist
├── references/context.md   → Target folders + code examples + patterns
├── templates/checklist.md  → Step-by-step execution checklist
└── agents/openai.yaml      → Codex/OpenAI metadata
.claude/skills/{name}/
└── SKILL.md                → Claude wrapper (auto-generated)
```

After creating or modifying skills:

```bash
bun run skills:sync      # sync Claude wrappers from source of truth
bun run skills:validate  # validate all skill assets
```

### Adding Training Data / Code Examples

Use the `skill-add-example` skill to add real code examples as agent references.

**Claude:** `/skill-add-example` &nbsp;|&nbsp; **Codex:** `$skill-add-example`

Examples are stored in `.agents/examples/`:

```
.agents/examples/
└── {skill-name}/
    └── {framework-or-context}/
        └── {example-name}/
            ├── page.tsx
            └── hooks/
```

Each example must be referenced in the related skill's `references/context.md` so the agent can find it during execution.

---

## Vibe Coding Flow

Feature development in this repo uses AI agents. Planning is handled by [OpenSpec](https://github.com/Fission-AI/OpenSpec), implementation is guided by **skills** — structured instructions the agent reads before executing tasks.

**All feature work must follow the OpenSpec workflow.**

Why:
- **Structured thinking** — forces upfront design before implementation, reducing rework and scope creep
- **Traceability** — every feature has documented proposal, specs, design, and tasks in `openspec/changes/`
- **Quality assurance** — changes are reviewed against specs before archiving
- **Context preservation** — future developers and AI agents can understand why decisions were made
- **Collaboration** — clear handoff between propose → implement → verify phases

Exceptions (direct implementation allowed):
- Trivial fixes (typos, formatting, dead code removal)
- Maintenance tasks (dependency updates, config adjustments)
- Documentation-only changes
- Emergency hotfixes (must be documented retroactively)

### Phase 1 — Propose (OpenSpec)

Turn a feature idea into a proposal, specs, design, and task list.

```
Trigger: /opsx:propose "feature name"
Output:  openspec/changes/{slug}/
           proposal.md
           specs/
           design.md
           tasks.md
```

---

### Phase 2 — Implementation (per task)

Execution order per feature:

#### 2a. FE Slicing
> Skill: `web-slicing`

Implement UI from design/description — no real data yet, use dummy.

```
Target: apps/web/app/(group)/[feature]/
Output: page.tsx + [feature]-content.tsx
```

#### 2b. Backend + OpenAPI
> Skill: `api-feature` + `docs-openapi`

Implement Clean Architecture in FastAPI: entity → use case → repository → router.
FastAPI routers and Pydantic models generate the OpenAPI artifact.

```
Target: apps/api/app/
         docs/openapi.json
```

#### 2c. FE ↔ API Integration
> Skill: `web-api-integrated`

Create Zod schemas, response types, constants, and react-query hooks. Wire the sliced UI to the running API.

```
Target: packages/schemas/
         packages/types/
         apps/web/hooks/transactions/use-{domain}/
         apps/web/constants/
```

---

### Phase 3 — Verify & Archive (OpenSpec)

```
Trigger: /opsx:verify     → validate implementation
         /opsx:archive    → archive specs after completion
```

## MCP Setup for AI Agents

Required MCP for this repo:
- `github`

Configuration is read from `.mcp.json` at the repo root. This file is gitignored since it contains real tokens/credentials.

If you just cloned this repo:
1. Create `.mcp.json` with your GitHub token
2. Fill in `.agents/settings.json` for `repo.owner` and `repo.name`
3. Run `bun run session:status`
4. Start with OpenSpec or resume an active task

## Contributing

Contributions welcome.

Recommended workflow:
1. Fork or create a new branch from `main`
2. Run `bun install`
3. Run `bun run bootstrap`
4. Make your changes
5. Ensure `bun run check` passes
6. If touching skills / `.agents`, also run `bun run skills:sync` and `bun run skills:validate`
7. Open a pull request

For OpenAPI documentation changes:
1. Edit FastAPI routers and Pydantic models
2. Run `bun run openapi:generate`
3. Commit the generated `docs/openapi.json`

For skill changes:
1. Edit source of truth in `.agents/skills/*`
2. Run `bun run skills:sync`
3. Validate with `bun run skills:validate`

## License

This repo is licensed under [MIT](./LICENSE).
