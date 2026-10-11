## MODIFIED Requirements

### Requirement: Multi-hop decomposition is opt-in and evaluation-gated

The system SHALL keep LLM-driven multi-query, HyDE, step-back, and multi-hop decomposition
opt-in and evaluation-gated, while storing its operational configuration at Project scope.
The effective Project setting SHALL apply uniformly to all Knowledge Bases in that Project.
It MUST bound decomposition depth and MUST NOT make decomposition default behavior until the
evaluation gate is met and reviewed.

#### Scenario: Project enables bounded decomposition
- **WHEN** a Project has an approved decomposition configuration and a query selects one or more member Knowledge Bases
- **THEN** decomposition uses the Project bounds and records the Project configuration version

#### Scenario: Decomposition would exceed the bounded depth
- **WHEN** a multi-hop plan exceeds the configured maximum decomposition depth
- **THEN** the system truncates the plan to the Project bound, proceeds only with permitted sub-queries, and records the truncation

#### Scenario: Project configuration is not approved
- **WHEN** a Project has no approved evaluation result for decomposition
- **THEN** the query does not enable LLM-driven decomposition by default
