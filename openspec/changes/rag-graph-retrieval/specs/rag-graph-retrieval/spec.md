## ADDED Requirements

### Requirement: Graph retrieval is tenant- and ACL-scoped per hop
The system SHALL traverse tenant- and ACL-scoped entity/relationship graphs alongside
dense/sparse vector retrieval only when a versioned graph schema exists and every hop
applies mandatory ACL predicates. It MUST NOT relax tenant, classification, or
active-generation filters at any hop and MUST NOT replace the default evidence path.

#### Scenario: Graph hop crosses an unauthorized boundary
- **WHEN** a graph traversal hop reaches an entity outside the tenant, ACL, or
  classification clearance scope
- **THEN** the system excludes that entity and its downstream hops from retrieval
  evidence without exposing it to the answer

#### Scenario: Traversal exceeds the bounded depth or node budget
- **WHEN** a graph traversal reaches the configured maximum hop depth or node budget
- **THEN** the system truncates the traversal at that boundary, records the truncation
  in the trace, and proceeds with the evidence collected so far

#### Scenario: No versioned graph schema is installed
- **WHEN** the graph traversal executor starts and no versioned graph schema is present
- **THEN** the executor is a no-op and the pipeline runs on vector results only without
  surfacing an error to the caller

#### Scenario: Graph schema version is unknown
- **WHEN** the graph traversal executor encounters a graph schema version it does not
  recognise
- **THEN** the executor refuses to run, logs the version mismatch, and the pipeline
  falls back to vector results only

### Requirement: Graph evidence is merged additively before grounded generation
The system SHALL convert graph-retrieved nodes to the same evidence format as vector
results and merge them into the retrieval result set before the calibrated-evidence
decision and grounded-generation steps. The generation and streaming pipeline MUST NOT
be modified to distinguish between vector and graph evidence sources.

#### Scenario: Graph traversal returns no results
- **WHEN** graph traversal completes and returns an empty node set
- **THEN** the pipeline continues with vector results only; no error is surfaced to the
  caller and no change is made to the generation step
