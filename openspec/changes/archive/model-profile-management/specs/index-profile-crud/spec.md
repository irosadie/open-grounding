## ADDED Requirements

### Requirement: Create index profile
The system SHALL allow authenticated tenant members to create an index profile combining a dense embedding profile, optional sparse profile, chunking strategy, and Qdrant collection config.

#### Scenario: Successful creation
- **WHEN** user submits valid name, embedding_profile_id, collection, dimensions, chunking_strategy
- **THEN** system creates the index profile and returns it

#### Scenario: Mismatched dimensions rejected
- **WHEN** user submits dimensions that don't match the referenced embedding model's output
- **THEN** system returns VALIDATION_ERROR

### Requirement: Set active index profile
The system SHALL allow setting one index profile as active per tenant. Only the active profile is used for new ingestion jobs.

#### Scenario: Set active
- **WHEN** user sets an index profile as active
- **THEN** system marks it ACTIVE and marks all other profiles as INACTIVE

#### Scenario: Only one active at a time
- **WHEN** tenant already has an active profile and user sets a different one as active
- **THEN** previous active profile becomes INACTIVE, new one becomes ACTIVE

### Requirement: List index profiles
The system SHALL return all index profiles for the tenant with their current status.

#### Scenario: Active profile marked in list
- **WHEN** user lists index profiles
- **THEN** the active profile has is_active=true, all others have is_active=false
