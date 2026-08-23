## MODIFIED Requirements

### Requirement: Adapter injects X-Api-Key header when api_key is set
`DoclingServeAdapter` SHALL accept an optional `api_key: str | None` constructor
parameter. When `api_key` is not `None`, every HTTP request (submit, poll, result)
MUST include the header `X-Api-Key: {api_key}`. When `api_key` is `None`, no
authentication header is added.

#### Scenario: API key injected on all requests
- **WHEN** adapter is constructed with `api_key="secret"`
- **THEN** every HTTP request to docling-serve includes `X-Api-Key: secret` header

#### Scenario: No header when api_key is None
- **WHEN** adapter is constructed with `api_key=None`
- **THEN** no `X-Api-Key` header is added to any request

### Requirement: Parse stage decrypts KB api key and passes to adapter
The parse stage SHALL call `get_api_key_decrypted()` to obtain the plain-text key
for the KB before constructing `DoclingServeAdapter`. The decrypted key MUST be
passed as `api_key` to the adapter. The key MUST NOT be logged.

#### Scenario: Decrypted key passed to adapter
- **WHEN** KB config has a stored encrypted API key
- **THEN** parse stage decrypts it and passes it to `DoclingServeAdapter(api_key=...)`

#### Scenario: No key stored — adapter constructed without api_key
- **WHEN** KB config has no stored API key
- **THEN** `DoclingServeAdapter` is constructed with `api_key=None`
