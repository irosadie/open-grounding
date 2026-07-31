# api-contract-compatibility Specification

## Purpose
TBD - created by archiving change migrate-api-to-fastapi. Update Purpose after archive.
## Requirements
### Requirement: Success response envelope is compatible
The system SHALL return successful API responses using `success: true`, `message`, and optional `data` and `meta` fields. The API base URL and existing system paths MUST remain unchanged for the Next.js proxy.

#### Scenario: Client receives successful login response
- **WHEN** credentials are accepted at `/auth/login`
- **THEN** the response uses the success envelope and contains the documented user and token data

### Requirement: Error response envelope is compatible
The system SHALL translate domain, authentication, validation, and unhandled errors into `success: false` error envelopes. Validation failures MUST use HTTP 422, and the response MUST include machine-readable error codes and affected paths where available.

#### Scenario: Client submits invalid registration payload
- **WHEN** a client posts an invalid payload to `/auth/register`
- **THEN** the service responds with HTTP 422 and an error envelope rather than FastAPI's default validation body

### Requirement: JWT and password compatibility is preserved
The system SHALL issue and validate JWTs with the existing claim names, issuer, audience, and expiry policy. It MUST validate legacy Node scrypt password hashes in addition to the password format used for newly created accounts.

#### Scenario: Existing account logs in
- **WHEN** a user has a valid password hash created by the prior Node API
- **THEN** the user can authenticate successfully through FastAPI with the same password

### Requirement: OpenAPI is generated from FastAPI
The system SHALL generate its OpenAPI schema from the FastAPI application and export the generated document to `docs/openapi.json` for existing documentation tooling.

#### Scenario: API documentation is generated
- **WHEN** the documented OpenAPI generation command runs
- **THEN** `docs/openapi.json` reflects the FastAPI system and authentication operations

### Requirement: Backend behavior is verified with Pytest
The system SHALL use Pytest for backend unit and HTTP contract tests. Test coverage MUST include system routes, success/error envelopes, authentication access rules, and database repository behavior.

#### Scenario: Backend checks run
- **WHEN** the documented backend test command is run
- **THEN** Pytest executes the API unit and HTTP contract test suite successfully

