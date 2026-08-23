---
name: api-bugfix
description: Fix backend bugs with minimal touch, keep other layers stable, then sync Pydantic schemas, DTO, OpenAPI, and tests when behavior is affected.
---

# Skill: API Bugfix

## Context (Required)
- Folder scope + impact map: `references/context.md`
- Execution checklist: `templates/checklist.md`

Use this skill when the user asks to fix a backend bug. Core principle: **minimal touch**. Find the root cause, change as little as possible, keep layering clean, then sync Pydantic schemas, DTO, OpenAPI, and tests when endpoint behavior is actually affected.

## Workflow

### 1. Reproduce or Define the Bug Clearly

Before changing code:
- understand the symptom
- identify the failing behavior in route handler, service, use case, or repository
- locate the boundary: request validation, business rule, response mapping, repository, or side effect

When possible, add or modify a test that represents the bug.

### 2. Localize the Root Cause

Find the smallest possible root cause. Prioritize by location:
- route handler / Pydantic schema if the bug is in request parsing
- service if the bug is in orchestration or response shaping
- use case if the bug is business logic
- repository / infrastructure if the bug is in persistence or external side effect

Do not rewrite multiple layers when one layer is enough to fix the bug.

### 3. Apply a Minimal Fix

Minimal touch rules:
- touch as few files as possible
- preserve the `route handler → service → use case → repository` boundary
- do not refactor unrelated layers
- do not rename or restructure just because the file is open

### 4. Sync Contract and Docs That Are Affected

If the fix changes endpoint behavior, request shape, response shape, or error semantics, update what is actually needed:
- Pydantic request schema (`interfaces/http/schemas.py`)
- DTO / Pydantic response model (`application/dtos.py`)
- OpenAPI spec via `uv run python -m app.export_openapi`
- relevant tests

Do not let endpoint behavior change while OpenAPI stays stale.

### 5. Verify Narrowly but Thoroughly

Minimum verification:
- test that reproduces or guards the bug
- `uv run ruff check app tests` on the touched surface
- `uv run mypy app` on the touched surface
- `uv run python -m app.export_openapi` if the contract changed
- confirm no new drift between code and OpenAPI

## Prohibitions

- **NEVER** refactor across layers when the user's goal is only a bugfix.
- **NEVER** change unrelated files "while you're at it".
- **NEVER** let Pydantic schema/DTO/OpenAPI drift when the fix changes endpoint behavior.
- **NEVER** move business logic into the HTTP layer for a quick fix.
- **NEVER** finish without targeted verification.

## Pre-Completion Checklist

- [ ] Bug reproduced or faulty behavior defined clearly
- [ ] Root cause localized to the smallest reasonable layer
- [ ] Changes remain minimal touch
- [ ] Pydantic schema/DTO/OpenAPI updated when affected
- [ ] Relevant tests added or updated
- [ ] `uv run python -m app.export_openapi` run if contract changed
- [ ] `uv run ruff check app tests` passes
- [ ] `uv run mypy app` passes
- [ ] No new drift in backend contract
- [ ] All files end with a newline (EOF)
