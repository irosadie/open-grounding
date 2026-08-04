## ADDED Requirements

### Requirement: Context construction rechecks source authorization
The system SHALL re-apply tenant, ACL, classification, active-version, and time policy
when fetching canonical chunks, parent context, neighboring content, or source
artifacts for selected candidates. Parent expansion MUST remain within the permitted
document generation.

#### Scenario: Selected child has an inaccessible parent
- **WHEN** a selected child candidate would expand to a parent that is no longer
  permitted by policy
- **THEN** the parent is excluded and the system continues only with permitted evidence

### Requirement: Evidence context is bounded and source-safe
The system SHALL reserve system and output token budgets, remove duplicate/low-value
content, preserve useful source diversity, and treat retrieved text as untrusted data.
Instruction-like text from a source MUST NOT alter system, authorization, or generation
policy.

#### Scenario: Retrieved source contains instructions
- **WHEN** selected evidence includes text that attempts to instruct the model or user
- **THEN** the context builder isolates it as source data and generation policy remains
  unchanged

### Requirement: Citations are stable evidence identifiers
The system SHALL assign stable citation IDs to selected evidence and retain document,
version, title, locator, and bounded supporting snippet metadata. Every material
factual claim in a final answer MUST reference valid selected citation IDs.

#### Scenario: Answer cites a selected PDF passage
- **WHEN** a final answer uses a factual claim supported by a PDF chunk
- **THEN** its citation resolves to the permitted document version, title, and page or
  section locator selected in the evidence context
