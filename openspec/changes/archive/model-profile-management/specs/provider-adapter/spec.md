## ADDED Requirements

### Requirement: Provider health check
The system SHALL expose a health check per provider that verifies connectivity and model availability.

#### Scenario: Healthy provider
- **WHEN** provider is reachable and model is available
- **THEN** health check returns status=ok with latency_ms

#### Scenario: Unhealthy provider
- **WHEN** provider is unreachable or returns error
- **THEN** health check returns status=error with error message (no credentials exposed)

### Requirement: Fallback chain on embedding failure
The system SHALL attempt fallback providers in order when primary embedding provider fails.

#### Scenario: Primary fails, fallback succeeds
- **WHEN** primary embedding provider returns error
- **THEN** system retries with next provider in fallback chain and logs the fallback event

#### Scenario: All providers fail
- **WHEN** all providers in fallback chain fail
- **THEN** ingestion job moves to FAILED state with error code EMBEDDING_PROVIDER_UNAVAILABLE

### Requirement: Supported providers
The system SHALL support at minimum: FastEmbed (local, no key), OpenAI (API key), Ollama (local endpoint).

#### Scenario: FastEmbed works without API key
- **WHEN** FastEmbed provider is configured with a supported model name
- **THEN** embeddings are generated locally without any API key

#### Scenario: OpenAI requires API key
- **WHEN** OpenAI provider is configured without OPENAI_API_KEY env var
- **THEN** provider health check returns status=error with message "API key not configured"
