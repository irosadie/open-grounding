## Context

The ingestion quality gate (`QualityGate` in `apps/api/app/domain/rag/normalizer.py`) currently uses hardcoded constructor defaults. One parameter — `max_invalid_char_ratio` — is declared but never evaluated in `evaluate()`, meaning OCR-corrupted documents can silently reach `READY`. There is no per-KB configuration surface and no way for operators to mandate human review without patching code.

The KB entity (`rag_knowledge_bases`) exists and is fully persisted. Related configs (Decomposition, Planner, Memory) follow a pattern: separate table with `knowledge_base_id` FK, dedicated domain entity, repository protocol, and CRUD endpoints. This change follows the same pattern.

The frontend KB list page uses scattered action buttons per KB (Planner, Memory) linking to independent routes with no shared layout. This pattern breaks down as more config surfaces are added.

## Goals / Non-Goals

**Goals:**
- Fix `max_invalid_char_ratio` bug in `QualityGate.evaluate()`
- Add `IngestionConfig` as a per-KB entity (DB + domain + repo + API)
- Apply per-KB config in the parse stage pipeline
- Add `auto_review` flag that forces all documents to `NEEDS_REVIEW` post-parse
- Build KB detail layout with tab shell (`[id]/layout.tsx`)
- Add Ingestion Settings tab UI with form to read/write `IngestionConfig`
- Refactor KB list page to single "Open" entry per KB

**Non-Goals:**
- Re-processing already-`READY` documents when config changes
- Per-document or per-source override of ingestion config
- Audit log for config changes (future)
- Real-time config reload for in-flight jobs (config is read at job start)

## Decisions

### D1: Separate `rag_kb_ingestion_configs` table (not JSON column on KB)

Follows the existing pattern for `DecompositionConfig`, `PlannerConfig`, `MemoryConfig` — each has its own table with `knowledge_base_id` FK. Avoids schema migrations on the KB table itself. Config fields are typed columns, not a JSON blob, giving type safety and indexability.

Alternative considered: JSON column on `rag_knowledge_bases`. Rejected — not consistent with existing pattern, loses type safety, harder to query/validate at DB level.

### D2: Upsert semantics on PUT (create-or-update)

GET returns defaults if no record exists. PUT upserts. This avoids requiring a separate POST-then-PUT flow and matches the pattern used by PlannerConfig and DecompositionConfig endpoints in this codebase.

Alternative considered: explicit POST to create + PUT to update. Rejected — unnecessary complexity for a singleton-per-KB resource.

### D3: Config read at job start, not cached per pipeline run

The parse stage reads `IngestionConfig` once at the start of the job via the repository. No in-memory cache. If config changes mid-job, the current job uses the config it read at start — acceptable because jobs are short-lived.

Alternative considered: pass config as part of the job payload at enqueue time. Rejected — makes re-queued retries use stale config, increases job payload size.

### D4: `auto_review` overrides quality gate outcome, quality evidence still computed

When `auto_review=true`, the parse stage routes to `NEEDS_REVIEW` regardless of quality gate result. Quality metrics are still computed and persisted for operator visibility. The quality gate result is recorded as evidence but does not affect routing.

Alternative considered: skip quality gate entirely when `auto_review=true`. Rejected — operators benefit from seeing quality scores even when reviewing manually.

### D5: KB detail layout at `[id]/layout.tsx` with segment-derived active tab

Next.js App Router layout file wraps all `[id]/*` sub-routes. Active tab is derived from `usePathname()` — no local state needed. Existing sub-routes (`/planner`, `/memory`, `/decomposition`) work unchanged inside the new layout.

Alternative considered: client-side tab state with a single page. Rejected — breaks direct linking, back/forward navigation, and URL sharing.

### D6: KB list default landing tab is `/planner`

"Open" button on list page links to `/{id}/planner` as the first tab. Consistent with current Planner button behavior, minimizes navigation change for existing users.

## Risks / Trade-offs

- **[Risk] Existing Planner/Memory direct links break** if users have bookmarks to `/console/knowledge-bases/{id}/planner` standalone.
  → Mitigation: these routes still exist and render correctly inside the new layout — no redirect needed. Deep links still work.

- **[Risk] Parse stage adds one extra DB read per job** (fetching IngestionConfig).
  → Mitigation: single indexed PK lookup by `knowledge_base_id` — negligible latency. No N+1.

- **[Risk] `auto_review=true` dramatically increases human workload** if enabled on a high-volume KB by mistake.
  → Mitigation: default is `false`. UI renders a clear warning label when enabled. No bulk-enable mechanism.

- **[Risk] Invalid char ratio computation requires full text scan of all elements**.
  → Mitigation: already done in `compute_quality()` loop — add ratio computation there, not as a separate pass.

## Migration Plan

1. Add Alembic migration: create `rag_kb_ingestion_configs` table
2. No data migration needed — GET returns defaults for KBs without a record
3. Deploy backend: new table + endpoints + quality gate fix + parse stage reads config
4. Deploy frontend: new layout + ingestion tab + KB list refactor
5. Rollback: revert frontend deploy (no UI change visible), then revert backend (table is additive, no existing data affected, parse stage falls back to defaults if table is dropped)

## Open Questions

- None — all decisions confirmed with user before proposal.
