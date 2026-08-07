## ADDED Requirements

### Requirement: Tenant can query count of documents pending review
The system SHALL expose an authenticated endpoint that returns the total count of
document versions in `NEEDS_REVIEW` state for the active tenant. The count MUST be
scoped strictly to the requesting tenant and MUST NOT include versions from other
tenants.

#### Scenario: Tenant has documents pending review
- **WHEN** an authorized caller requests the pending review count and there are document versions in `NEEDS_REVIEW` state for that tenant
- **THEN** the API returns the exact count of those versions

#### Scenario: Tenant has no documents pending review
- **WHEN** an authorized caller requests the pending review count and there are no document versions in `NEEDS_REVIEW` state
- **THEN** the API returns a count of zero

#### Scenario: Unauthenticated request
- **WHEN** an unauthenticated caller requests the pending review count
- **THEN** the API returns 401
