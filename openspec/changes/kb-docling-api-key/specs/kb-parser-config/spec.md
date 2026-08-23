## MODIFIED Requirements

### Requirement: IngestionConfig stores encrypted docling-serve API key
The `IngestionConfig` domain entity SHALL include `docling_serve_api_key_enc: str | None`
field containing the AES-256-GCM encrypted API key. The plain-text key MUST NOT be
stored anywhere in the domain entity. `INGESTION_CONFIG_DEFAULTS` MUST set
`docling_serve_api_key_enc=None`.

#### Scenario: Default config has no API key
- **WHEN** `INGESTION_CONFIG_DEFAULTS` is used
- **THEN** `docling_serve_api_key_enc` is `None`

#### Scenario: API key is stored encrypted
- **WHEN** admin upserts config with a plain-text `docling_serve_api_key`
- **THEN** `IngestionConfig.docling_serve_api_key_enc` contains the AES-256-GCM
  encrypted value, not the plain-text key

### Requirement: Service encrypts API key on write and decrypts for worker
`IngestionConfigService.upsert_config()` SHALL accept `docling_serve_api_key: str | None`
(plain text), encrypt it via `crypto.encrypt()` using `get_encryption_key(settings)`,
and persist the encrypted value. A new internal method
`get_api_key_decrypted(*, tenant, knowledge_base_id, settings) -> str | None` SHALL
decrypt and return the key for worker use only. This method MUST NOT be called from
any HTTP route handler.

#### Scenario: Key is encrypted before persist
- **WHEN** `upsert_config()` is called with `docling_serve_api_key="secret"`
- **THEN** the persisted `docling_serve_api_key_enc` is the encrypted form, not `"secret"`

#### Scenario: Worker can decrypt key
- **WHEN** `get_api_key_decrypted()` is called for a KB with a stored key
- **THEN** it returns the original plain-text key

#### Scenario: Clearing key sets enc to None
- **WHEN** `upsert_config()` is called with `docling_serve_api_key=None`
- **THEN** `docling_serve_api_key_enc` is set to `None`

### Requirement: DB column stores encrypted key
The `rag_kb_ingestion_configs` table SHALL gain a `docling_serve_api_key_enc`
column of type `TEXT NULL`. Migration MUST be reversible.

#### Scenario: Migration applies cleanly
- **WHEN** Alembic upgrade runs
- **THEN** column is added with `NULL` for all existing rows

#### Scenario: Migration is reversible
- **WHEN** Alembic downgrade runs
- **THEN** column is dropped without affecting other columns
