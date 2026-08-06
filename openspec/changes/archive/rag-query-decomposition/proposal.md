# Proposal: RAG Query Decomposition

## Problem

The current grounded query pipeline handles one query → one retrieval → one generation.
This breaks down for complex, multi-intent queries like:

> "What is the difference between department A and B leave policies, and how does it affect productivity?"

A single retrieval pass misses evidence scattered across semantically distinct sub-topics.
The result is incomplete answers, low recall, and hallucinated bridges between evidence gaps.

## Proposed Solution

A **hybrid query decomposition pipeline** that:

1. Scores query complexity linguistically (fast, zero-cost)
2. Only triggers LLM decomposition when complexity exceeds a configurable threshold
3. Runs sub-retrievals concurrently
4. Deduplicates and merges evidence before generation
5. Is fully configurable per knowledge base — model, prompt, guardrails

This is opt-in per request and per knowledge base. The existing grounded query pipeline
remains the default and is never affected.

## Key Design Decisions

- **Hybrid approach**: linguistic pre-screening gates LLM decomposer calls — no unnecessary LLM cost for simple queries
- **Per-KB config**: `DecompositionConfig` entity attached to each knowledge base, not global
- **ModelProfile reuse**: decomposer LLM selected from existing `ModelProfile` registry
- **Jinja2 prompt templates**: system + user prompt fully customizable per KB
- **Bounded depth**: `max_sub_queries` (1-5) and `max_depth` (1-3) enforced at runtime
- **Full trace visibility**: each sub-query, its retrieved evidence, and merge decisions recorded in existing trace system
- **Guardrails as JSON**: extensible per-KB guardrail config (min complexity score, blocked patterns, etc.)

## What This Is Not

- Not a default behavior change — existing pipeline untouched
- Not a graph retrieval or multi-hop reasoning feature
- Not a conversation memory feature
- Not a replacement for good indexing — decomposition amplifies retrieval, not fixes bad chunks

## Success Criteria

- Complex multi-intent queries return higher recall answers with evidence from multiple sub-topics
- Simple queries bypass decomposition with zero latency overhead
- Every decomposition decision is traceable
- Config UI available in console for per-KB setup
- All existing tests pass; new tests cover decomposition path

## Scope

**In scope:**
- `DecompositionConfig` entity + DB migration
- Complexity scorer (linguistic)
- LLM decomposer with Jinja2 prompt templates
- Parallel sub-retrieval + evidence dedup/merge
- Trace integration
- API: CRUD for DecompositionConfig per KB
- Frontend: config UI under KB settings
- Shared Zod schemas + types

**Out of scope:**
- Graph retrieval
- Live tool execution
- Long-term memory
- Numeric confidence scoring
