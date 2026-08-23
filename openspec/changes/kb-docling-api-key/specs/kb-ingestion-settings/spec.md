## MODIFIED Requirements

### Requirement: API write request accepts docling_serve_api_key (write-only)
The ingestion config upsert endpoint SHALL accept `docling_serve_api_key: str | None`
in the request body. This field is write-only — it MUST NOT appear in any response.
Sending `null` clears the stored key. Sending a non-empty string replaces the key.

#### Scenario: Key submitted in write request
- **WHEN** client PUTs with `{"docling_serve_api_key": "mykey", ...}`
- **THEN** the key is stored encrypted and not echoed back in the response

#### Scenario: Key cleared by sending null
- **WHEN** client PUTs with `{"docling_serve_api_key": null, ...}`
- **THEN** stored key is cleared

### Requirement: API response exposes docling_serve_api_key_set boolean
The ingestion config GET and upsert response SHALL include
`docling_serve_api_key_set: bool` — `true` when an encrypted key is stored,
`false` otherwise. The plain-text key MUST NEVER appear in any response.

#### Scenario: GET response shows key set indicator
- **WHEN** a KB has a stored API key
- **THEN** GET response returns `"doclingServeApiKeySet": true`
- **AND** no `docling_serve_api_key` field appears in the response

#### Scenario: GET response shows key not set
- **WHEN** no API key is stored for a KB
- **THEN** GET response returns `"doclingServeApiKeySet": false`
