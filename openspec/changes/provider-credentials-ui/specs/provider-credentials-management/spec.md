## ADDED Requirements

### Requirement: Set provider credential
The system SHALL allow authenticated tenant members to set a provider credential (API key, base URL, token) via the UI. The credential SHALL be encrypted before storage and SHALL never be returned in any API response.

#### Scenario: Successful set
- **WHEN** user submits a valid provider credential via the UI
- **THEN** system encrypts and stores the credential, returns `{isConfigured: true, updatedAt}`

#### Scenario: Update existing credential
- **WHEN** user submits a new value for an already-configured credential
- **THEN** system overwrites the encrypted value, returns updated timestamp

#### Scenario: Empty value rejected
- **WHEN** user submits an empty string as credential value
- **THEN** system returns VALIDATION_ERROR

### Requirement: Check credential status
The system SHALL return configuration status for all supported providers without exposing the credential value.

#### Scenario: Configured provider shows status
- **WHEN** user requests provider credential status
- **THEN** response contains `{provider, keyName, isConfigured: true, updatedAt}` — value field is NEVER present

#### Scenario: Unconfigured provider shows status
- **WHEN** provider has no credential set in DB and no env var fallback
- **THEN** response contains `{provider, keyName, isConfigured: false}`

### Requirement: Revoke provider credential
The system SHALL allow revoking a stored credential, which sets is_active=false and clears the encrypted value.

#### Scenario: Successful revoke
- **WHEN** user revokes a configured credential
- **THEN** system clears the stored value, returns `{isConfigured: false}`

### Requirement: Provider registry reads from DB first
The system SHALL read provider credentials from DB (decrypted) before falling back to env vars.

#### Scenario: DB credential takes precedence over env
- **WHEN** both DB credential and env var are set for the same provider
- **THEN** DB credential is used

#### Scenario: Env fallback when DB has no credential
- **WHEN** DB has no credential for a provider but env var is set
- **THEN** env var value is used transparently

### Requirement: Credentials encrypted at rest
All stored credential values SHALL be encrypted using AES-256-GCM with a random IV per write.

#### Scenario: Value in DB is never plaintext
- **WHEN** a credential is stored
- **THEN** the `value_enc` column contains base64-encoded encrypted data, never the raw key

#### Scenario: Decryption uses SECRET_KEY env var
- **WHEN** provider registry reads a credential from DB
- **THEN** decryption uses the `SECRET_KEY` env var (fallback: `JWT_SECRET`)
