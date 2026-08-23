## ADDED Requirements

### Requirement: Create knowledge base
The system SHALL allow authenticated tenant members to create a new knowledge base with a name and slug.

#### Scenario: Successful creation
- **WHEN** user submits a valid name and slug
- **THEN** system creates the knowledge base with status ACTIVE and returns the new KB data

#### Scenario: Duplicate slug rejected
- **WHEN** user submits a slug that already exists in the same tenant
- **THEN** system returns a CONFLICT error

#### Scenario: Invalid slug format rejected
- **WHEN** user submits a slug with invalid characters (not kebab-case)
- **THEN** system returns a VALIDATION_ERROR

### Requirement: List knowledge bases
The system SHALL return all ACTIVE knowledge bases belonging to the authenticated user's tenant.

#### Scenario: List returns tenant-scoped KBs
- **WHEN** authenticated user requests knowledge base list
- **THEN** system returns only KBs belonging to the user's tenant

#### Scenario: Empty list
- **WHEN** tenant has no knowledge bases
- **THEN** system returns an empty array with success true

### Requirement: Delete knowledge base
The system SHALL allow authenticated tenant members to soft-delete a knowledge base by setting its status to ARCHIVED.

#### Scenario: Successful soft delete
- **WHEN** user deletes an existing KB
- **THEN** system sets KB status to ARCHIVED and returns success

#### Scenario: Delete non-existent KB
- **WHEN** user deletes a KB ID that does not exist or belongs to another tenant
- **THEN** system returns NOT_FOUND error
