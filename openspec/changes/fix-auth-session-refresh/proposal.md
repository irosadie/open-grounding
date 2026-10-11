## Why

The API issues a new refresh token but keeps the previous token hash in the persisted auth session. Once the web BFF refreshes an access token, the next refresh is rejected and the user is sent back to login with an expired-session state. The frontend auth declaration also still requires a `companyId` field that the current API no longer returns.

## What Changes

- Rotate and persist the refresh-token hash whenever a refresh succeeds, while rejecting replay of the previous token.
- Keep refresh-session validation and token-hash replacement atomic at the repository boundary.
- Align NextAuth user/session declarations and regression tests with the current API user response.
- Persist refreshed tokens from the streaming BFF route so subsequent stream requests use the rotated pair.
- Preserve the existing auth endpoints, required token claims, and error contract; add only a unique refresh-token identifier needed for deterministic rotation.

## Capabilities

### New Capabilities

### Modified Capabilities

- `fastapi-api-runtime`: a valid refresh token must produce a usable successor token and rotate the persisted session hash.
- `rag-console-app-shell`: the console's existing session-expiry recovery must continue to work after a successful refresh instead of failing on the next refresh.

## Impact

- API auth repository protocol, SQLAlchemy repository, refresh use case, and auth regression tests.
- NextAuth type declarations and auth callback tests in `apps/web`.
- No database migration is required because the existing `auth_sessions.token_hash` column is reused.
