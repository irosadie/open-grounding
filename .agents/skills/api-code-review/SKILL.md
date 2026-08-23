---
name: api-code-review
description: Review backend code with a senior lead standard, focused on bugs, regressions, contract drift, clean architecture risks, and test gaps in apps/api and related shared contracts.
---

# Skill: API Code Review

## Context (Required)
- Folder scope + key patterns: `references/context.md`
- Review checklist: `templates/checklist.md`

Use this skill when the user asks for review of backend changes, an API PR, or an audit of server-side implementation quality. Review like a senior lead: hunt bugs, regressions, contract drift, layering violations, and test gaps. Not a cosmetic review.

## Workflow

### 1. Define the Review Surface

Read the diff or target files, then map the relevant surface:
- `apps/api/app/interfaces/http`
- `apps/api/app/application`
- `apps/api/app/domain`
- `apps/api/app/infrastructure`
- `docs/openapi.json`

If the change touches an endpoint, Pydantic schema, DTO, or response shape, audit contract artifacts too.

### 2. Prioritize Real Risk

Find issues in this priority order:
1. functional bugs and endpoint regressions
2. clean architecture violations / boundary leakage
3. Pydantic schema, DTO, and OpenAPI drift
4. error handling and status code mismatch
5. wrong persistence / side effects
6. test gaps for important behavior

### 3. Audit Against Repo Standards

Check strictly:
- flow stays `route handler → service → use case → repository`
- request validation does not leak into the wrong layer
- repository Protocol and SQLAlchemy implementation stay aligned
- errors bubble to `@app.exception_handler(DomainError)`, not handled ad hoc
- request/response contract stays in sync with `docs/openapi.json`
- important behavior changes have relevant tests

### 4. Format the Review Output

The review **must** lead with findings, ordered by severity.

Format per finding:
- severity `[P1]`, `[P2]`, or `[P3]`
- short title
- affected file/area
- why this is a bug/risk/regression
- what should be fixed

After findings, you may add:
- open questions / assumptions
- residual risks or testing gaps
- brief change summary if needed

If no findings, state explicitly that there are none, then call out remaining risks or coverage gaps.

### 5. Do Not Silently Fix

This skill defaults to review, not implementation. Do not change code unless the user explicitly asks for a fix after the review.

## Prohibitions

- **NEVER** open a review with praise or summary before findings.
- **NEVER** focus on style nits with no real impact on correctness or maintainability.
- **NEVER** skip drift between endpoint behavior and OpenAPI.
- **NEVER** treat the layering as clean just because tests pass; verify boundaries explicitly.
- **NEVER** fix code silently when the user only asked for a review.

## Pre-Completion Checklist

- [ ] Review scope mapped from diff or target files
- [ ] Backend layering checked (route handler → service → use case → repository)
- [ ] Contract artifacts checked when endpoint changes
- [ ] Findings ordered by severity
- [ ] No summary ahead of findings
- [ ] If no findings, residual risk or test gap still called out
- [ ] All files end with a newline (EOF)
