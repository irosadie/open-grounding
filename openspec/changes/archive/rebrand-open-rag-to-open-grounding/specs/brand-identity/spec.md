## ADDED Requirements

### Requirement: Package names use open-grounding scope
All shared packages SHALL use the `@open-grounding` npm scope.

#### Scenario: Package import resolves correctly
- **WHEN** a source file imports from `@open-grounding/schemas`, `@open-grounding/types`, or `@open-grounding/utils`
- **THEN** TypeScript resolves the import without error

### Requirement: Project identifier is open-grounding
The root project name and all workspace package names SHALL use `open-grounding` as the identifier (replacing `vibecoding-starter`).

#### Scenario: Root package name is correct
- **WHEN** `package.json` at repo root is read
- **THEN** `name` field equals `"open-grounding"`

### Requirement: Docker containers use open-grounding prefix
All Docker container names defined in `docker-compose.yml` SHALL be prefixed with `open-grounding-`.

#### Scenario: Container name is correct
- **WHEN** `docker-compose.yml` is read
- **THEN** container names are `open-grounding-postgres`, `open-grounding-redis`, `open-grounding-qdrant`, `open-grounding-minio`

### Requirement: Database name is open_grounding
The PostgreSQL database name SHALL be `open_grounding`.

#### Scenario: DATABASE_URL uses correct DB name
- **WHEN** `apps/api/.env` or `.env.example` is read
- **THEN** `DATABASE_URL` contains `open_grounding` as the database name

### Requirement: UI brand displays Open Grounding
The console UI topbar, browser tab title, and page metadata SHALL display `Open Grounding Console` as the product name.

#### Scenario: Topbar shows correct brand
- **WHEN** user opens any console page
- **THEN** topbar displays `Open Grounding Console`

#### Scenario: Browser tab shows correct title
- **WHEN** user opens the app
- **THEN** browser tab title contains `open-grounding`
