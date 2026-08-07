# document-custom-metadata Specification

## Purpose
TBD - created by archiving change document-custom-metadata. Update Purpose after archive.
## Requirements
### Requirement: Document intake accepts optional flat key-value metadata
The system SHALL accept an optional `metadata` field in the intake request body.
`metadata` MUST be a flat object with string keys and string values.
The system MUST reject intake requests where `metadata` contains more than 20 keys,
any key exceeds 256 characters, or any value exceeds 256 characters.
Nested objects, arrays, and non-string values MUST be rejected with a validation error.

#### Scenario: Caller provides valid metadata at intake
- **WHEN** an authorized caller creates an intake request with a `metadata` field containing up to 20 string key-value pairs within character limits
- **THEN** the system accepts the request, persists the metadata on the document version, and returns the intake result normally

#### Scenario: Caller omits metadata at intake
- **WHEN** an authorized caller creates an intake request without a `metadata` field
- **THEN** the system accepts the request and the document version is created with null metadata

#### Scenario: Caller provides metadata exceeding key count limit
- **WHEN** an authorized caller creates an intake request with `metadata` containing more than 20 keys
- **THEN** the system rejects the request with a 422 validation error before creating any document or version record

#### Scenario: Caller provides metadata with oversized key or value
- **WHEN** an authorized caller creates an intake request with a metadata key or value exceeding 256 characters
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: Caller provides non-string metadata value
- **WHEN** an authorized caller creates an intake request with a metadata value that is not a string (e.g., number, boolean, object, array)
- **THEN** the system rejects the request with a 422 validation error

