# async-postgres-persistence Specification

## Purpose
TBD - created by archiving change migrate-api-to-fastapi. Update Purpose after archive.
## Requirements
### Requirement: API uses asynchronous PostgreSQL persistence
The system SHALL use SQLAlchemy 2 asynchronous engine and session APIs for API database operations. Repository implementations MUST satisfy the application's repository contracts without exposing ORM objects to domain or HTTP layers.

#### Scenario: Repository reads a user
- **WHEN** an application use case looks up a user by email or ID
- **THEN** the repository returns a domain user entity or no result using an asynchronous database session

### Requirement: Existing auth data model is preserved
The system SHALL preserve the PostgreSQL user and auth-session model, including UUID identifiers, unique user email, roles, statuses, password hashes, timestamps, and session ownership/expiry relationships.

#### Scenario: Existing user is accessed after migration
- **WHEN** FastAPI connects to a database containing a user created by the prior service
- **THEN** the user and associated auth sessions are readable without data transformation

### Requirement: Alembic owns API schema evolution
The system SHALL provide Alembic configuration and revisions for the API database schema. The initial migration MUST be safe for the schema-equivalent existing PostgreSQL model and MUST NOT delete user or session data.

#### Scenario: Migration is applied to an empty database
- **WHEN** a developer upgrades an empty PostgreSQL database with Alembic
- **THEN** the required enums, users table, auth-sessions table, constraints, and indexes are created

#### Scenario: Migration is prepared for an existing database
- **WHEN** a developer follows the documented migration procedure for a database created by the prior service
- **THEN** the database can be brought under Alembic version control without destructive schema changes

