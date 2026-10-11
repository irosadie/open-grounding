## MODIFIED Requirements

### Requirement: Authentication endpoints are available
The system SHALL expose register, login, logout, current-user, and refresh-token operations under `/auth`. Protected operations MUST require a valid Bearer access token and must reject suspended accounts or callers without an allowed role.

#### Scenario: User registers
- **WHEN** a client posts a valid name, email, and password to `/auth/register`
- **THEN** the service creates an active user and responds with HTTP 201 in the success envelope

#### Scenario: User logs in
- **WHEN** a client posts valid credentials to `/auth/login`
- **THEN** the service returns the user and an access/refresh token pair in the success envelope

#### Scenario: Authenticated user loads profile
- **WHEN** a caller with a valid access token sends `GET /auth/me`
- **THEN** the service returns the current user and active session information in the success envelope

#### Scenario: Access token is refreshed
- **WHEN** a client sends a valid refresh token to `/auth/refresh`
- **THEN** the service returns a new token pair compatible with the frontend proxy and persists the hash of the returned refresh token for the same active session

#### Scenario: Refresh token replay is rejected
- **WHEN** a client sends a refresh token that was already exchanged successfully
- **THEN** the service rejects it as invalid and does not replace the active session with a replayed token

