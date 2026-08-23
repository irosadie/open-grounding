# rag-conversation-memory Specification

## Purpose
TBD - created by archiving change rag-query-deferred-followups. Update Purpose after archive.
## Requirements
### Requirement: Long-term memory is retention-aware and opt-in
The system SHALL persist bounded user preferences or retrieved context as memory only
under a documented retention and redaction policy and explicit tenant opt-in. It MUST
NOT write retrieved source content into long-term memory by default and MUST NOT enable
autonomous background agents in this release.

#### Scenario: Memory write is not opt-in for the tenant
- **WHEN** a memory write is attempted and the tenant has not explicitly opted in
- **THEN** the system discards the memory write and continues the query without
  persisting any long-term memory
