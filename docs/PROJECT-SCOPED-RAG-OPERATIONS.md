# Project-scoped RAG operations

## Ownership model

`Project` is the control-plane boundary. A Project can own many Knowledge Bases, while
each active Knowledge Base has exactly one Project owner. Planner, Decomposition, Memory,
Answer Policy, and Guardrails are configured on the Project. Documents, ingestion,
parser/chunking, embeddings, indexes, sync, and diagnostics remain on the Knowledge Base.

Queries may send `project_id`, but the API remains authoritative. If it is omitted, the
server infers the Project only when every selected Knowledge Base has the same active
owner. A mismatch, archived Project, cross-tenant ID, or multi-Project selection fails
before planner, retrieval, MCP, memory, or generation side effects.

## Migration and review

Run the migration through the normal release pipeline:

```sh
cd apps/api
uv run python -m alembic upgrade head
```

The migration creates one tenant default Project, assigns existing active Knowledge Bases
to it, leaves documents/indexes/ACLs untouched, and creates bounded migration-review rows
for legacy configuration. The Project detail API exposes these rows as `migrationReviews`.
Do not silently select a winner when legacy Knowledge Base profiles conflict; an
administrator must save the intended Project profile.

## Compatibility controls

The following settings are temporary rollout controls:

- `RAG_PROJECT_LEGACY_FALLBACK_ENABLED`: permits single-KB reads to consult a legacy KB
  policy only when the Project has no profile.
- `RAG_PROJECT_LEGACY_KB_WRITES_ENABLED`: keeps old KB configuration writes available
  during the transition. Set it to `false` once Project profiles are populated.
- `RAG_PROJECT_COMPATIBILITY_END_DATE`: recorded operational cutoff for removing the
  compatibility path; it must be agreed before disabling the fallback globally.

Legacy writes are never used to override an existing Project profile, and multi-KB
requests never merge conflicting legacy profiles.

## Rollout and rollback

1. Apply the migration and verify `alembic current` reports `20260918_02`.
2. Review open migration rows per tenant and save Project-level configuration.
3. Observe `rag_project_*` structured metrics and query traces for scope conflicts and
   legacy fallback use.
4. Disable legacy writes, then disable legacy fallback after the compatibility window.
5. If application behavior must be rolled back, re-enable the compatibility settings and
   deploy the previous application version. Keep Project, membership, review, and audit
   rows; do not downgrade this migration in a shared or production database.

Project membership moves and policy changes are ADMIN-only, tenant-scoped, and audited
with bounded identifiers/reason codes. Audit metadata must never contain prompts,
provider credentials, source payloads, or tool arguments.
