## ADDED Requirements

### Requirement: Create model profile
The system SHALL allow authenticated tenant members to create a model profile specifying provider, model, kind, and dimensions.

#### Scenario: Successful creation
- **WHEN** user submits valid name, kind, provider, model, and dimensions
- **THEN** system creates the model profile with status ACTIVE and returns the new profile data

#### Scenario: Invalid kind rejected
- **WHEN** user submits an unsupported profile kind
- **THEN** system returns VALIDATION_ERROR

### Requirement: List model profiles
The system SHALL return all model profiles belonging to the authenticated tenant, grouped by kind.

#### Scenario: List returns tenant-scoped profiles
- **WHEN** authenticated user requests model profile list
- **THEN** system returns only profiles belonging to the user's tenant

### Requirement: Delete model profile
The system SHALL allow soft-delete of a model profile that is not referenced by any active index profile.

#### Scenario: Delete unreferenced profile
- **WHEN** user deletes a profile not used by any active index profile
- **THEN** system archives the profile and returns success

#### Scenario: Delete referenced profile rejected
- **WHEN** user attempts to delete a profile referenced by an active index profile
- **THEN** system returns CONFLICT error with message indicating which index profile references it
