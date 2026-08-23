## ADDED Requirements

### Requirement: Graph retrieval is tenant- and ACL-scoped per hop
The system SHALL traverse tenant- and ACL-scoped entity/relationship graphs alongside
dense/sparse vector retrieval only when a versioned graph schema exists and every hop
applies mandatory ACL predicates. It MUST NOT relax tenant, classification, or
active-generation filters at any hop and MUST NOT replace the default evidence path
until separately reviewed and promoted.

#### Scenario: Graph hop crosses an unauthorized boundary
- **WHEN** a graph traversal hop reaches an entity outside the tenant, ACL, or
  classification clearance scope
- **THEN** the system excludes that entity and its downstream hops from retrieval
  evidence without exposing it to the answer
