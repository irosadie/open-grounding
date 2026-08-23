## ADDED Requirements

### Requirement: FastAPI application uses Clean Architecture boundaries
The system SHALL run `apps/api` as a FastAPI application managed by Python tooling. It MUST keep domain, application, infrastructure, and HTTP-interface concerns separate, and HTTP routes MUST delegate business behavior to application services or use cases.

#### Scenario: API process starts
- **WHEN** a developer starts the API with the documented command and valid environment variables
- **THEN** a FastAPI service listens on the configured API port

#### Scenario: System information is requested
- **WHEN** a client sends `GET /`
- **THEN** the service returns a successful application-information envelope

### Requirement: System health endpoint remains available
The system SHALL expose `GET /health` without authentication and return the existing health response semantics from the FastAPI HTTP stack.

#### Scenario: Health check succeeds
- **WHEN** a client sends `GET /health`
- **THEN** the service responds with HTTP 200 and a successful envelope containing `status: "ok"`

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
- **THEN** the service returns a new token pair compatible with the frontend proxy
