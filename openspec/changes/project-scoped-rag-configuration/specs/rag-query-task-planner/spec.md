## MODIFIED Requirements

### Requirement: Planner is configurable per knowledge base via PlannerConfig

The system SHALL provide an optional versioned `PlannerConfig` per Project with: `enabled`,
`model_profile_id`, `system_prompt`, `user_prompt_template` (Jinja2), `max_tasks` (1–8),
`task_timeout_seconds` (1–60), `task_types` allowlist (RAG/MCP/GENERAL subset),
`mcp_enabled`, and `guardrails` JSON. API writes and reads SHALL use the Project scope.
Planner can be overridden per request only through the existing bounded `planner` request
override; that override MUST NOT change the owning Project or the selected Knowledge Bases.

#### Scenario: Project planner is used for several KBs
- **WHEN** a query selects multiple Knowledge Bases belonging to one Project with an active PlannerConfig
- **THEN** the planner uses that Project configuration and records its version in the trace

#### Scenario: Caller disables planner per-request
- **WHEN** a query payload contains `"planner": {"enabled": false}`
- **THEN** the system uses the standard single-pass pipeline without changing the Project PlannerConfig

#### Scenario: Legacy KB planner endpoint is used during compatibility
- **WHEN** a client reads a legacy Knowledge Base planner URL during the compatibility period
- **THEN** the service returns the owning Project configuration with explicit legacy/deprecation metadata and does not create a KB override

### Requirement: Planner config UI extends the decomposition settings page

The system SHALL provide a Query Planner settings page under the Project workspace with
the existing bounded model, prompt, task, timeout, type, MCP, guardrail, and task-run
viewer controls. The page SHALL identify the member Knowledge Bases affected by the
configuration and SHALL NOT render a per-KB PlannerConfig editor.

#### Scenario: Operator saves planner config
- **WHEN** an authorized administrator saves the Planner form in a Project workspace
- **THEN** the Project PlannerConfig is versioned and subsequent queries for every member KB use it
