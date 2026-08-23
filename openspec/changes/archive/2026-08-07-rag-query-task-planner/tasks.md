## 1. Domain — Task Model

- [x] 1.1 Buat domain models di `apps/api/app/domain/rag/task_plan.py`:
  - `TaskType` (RAG/MCP/GENERAL)
  - `TaskSpec` (typed task)
  - `TaskPlan`
  - `TaskResult` (envelope)
  - `ResumeResult`
- [x] 1.2 Buat `parse_task_plan(raw_json, max_tasks, allowed_types)` — validasi + truncation + fallback

## 2. API — Planner

- [x] 2.1 Upgrade `apps/api/app/application/query_decomposer.py` → `query_planner.py`:
  - Planner prompt menghasilkan task plan (bukan hanya sub-queries)
  - Template variabel: `{{ query }}`, `{{ max_tasks }}`, `{{ available_tools }}`, `{{ knowledge_base_name }}`
  - Reuse complexity scorer gating + model selection + fallback
- [x] 2.2 Buat `PlannerConfig` entity + repository (reuse pola DecompositionConfig)
- [x] 2.3 Migrasi: rename/duplicate `rag_decomposition_configs` → `rag_planner_configs` (atau extend existing dengan kolom task fields)
- [x] 2.4 Unit tests `tests/test_query_planner.py` (plan parsing, truncation, fallback, invalid JSON)

## 3. API — Async Executor

- [x] 3.1 Buat `apps/api/app/application/task_executor.py` — `TaskExecutor`
- [x] 3.2 Implementasi `asyncio.gather(return_exceptions=True)` + per-task `asyncio.timeout`
- [x] 3.3 Implementasi RAG executor — hybrid retrieval per task (fuse BM25 jika aktif)
- [x] 3.4 Implementasi GENERAL executor — LLM call tanpa evidence
- [x] 3.5 Implementasi MCP executor — dispatch ke `McpRuntimeService` (capability-gated, skip jika belum ada)
- [x] 3.6 Unit tests `tests/test_task_executor.py` (paralel, timeout isolation, error isolation)

## 4. API — Resume & Rerank

- [x] 4.1 Buat `apps/api/app/application/task_resumer.py` — `TaskResumer`
- [x] 4.2 Implementasi merge RAG evidence via `evidence_merger` + `gate_evidence` rerank
- [x] 4.3 Implementasi supplementary context blocks (MCP + GENERAL labeled)
- [x] 4.4 Implementasi abstain routing jika semua RAG gagal tanpa supplementary
- [x] 4.5 Unit tests `tests/test_task_resumer.py`

## 5. API — Pipeline Integration

- [x] 5.1 Update `rag_query_service.py` — planner gate → executor → resumer → generation
- [x] 5.2 Update trace — `planner`, `tasks`, `resume` metadata (REQ-6)
- [x] 5.3 Update `RagQueryRequest` schema — `planner` override (REQ-7)

## 6. API — PlannerConfig Service & Routes

- [x] 6.1 Buat `planner_config_service.py` — CRUD + validasi (model kind, Jinja2, bounds)
- [x] 6.2 Tambah DTOs: `CreatePlannerConfigRequest`, `PlannerConfigResponse`
- [x] 6.3 Routes: `GET/POST/DELETE /rag/knowledge-bases/{id}/planner` + `/defaults`
- [x] 6.4 Tambah DI ke `dependencies.py`

## 7. Shared Contracts

- [x] 7.1 Zod schema `plannerConfigSchema` di `packages/schemas/planner.ts`
- [x] 7.2 Response types `PlannerConfigResponse`, `PlannerDefaultsResponse` di `packages/types/planner-response.ts`

## 8. Frontend — Hooks

- [x] 8.1 Update `use-decomposition-config` → `use-planner-config` (atau tambah paralel): get/upsert/delete/defaults
- [x] 8.2 Update query payload builder — kirim `planner` override dari retrieval page

## 9. Frontend — UI

- [x] 9.1 Rename/extend page `.../[id]/decomposition` → `.../[id]/planner` dengan fields baru (task_types, mcp_enabled, task_timeout, available_tools hint)
- [x] 9.2 Tambah task run viewer di trace/retrieval page — task plan + status + resume summary
- [x] 9.3 Update link dari KB list

## 10. OpenAPI & Verification

- [x] 10.1 Regenerate `docs/openapi.json`
- [x] 10.2 Run `bun run typecheck` (web) — no errors
- [x] 10.3 Run `bun run lint` (web) — no errors
- [x] 10.4 Run `bun run test` (api) — all pass
- [ ] 10.5 Test end-to-end: enable planner → complex query → task plan terbentuk → RAG + GENERAL execute paralel → trace tampil
- [x] 10.6 Test fallback: MCP task tanpa runtime → status skipped + trace jelas
- [x] 10.7 Test fallback: planner gagal → single RAG task fallback
