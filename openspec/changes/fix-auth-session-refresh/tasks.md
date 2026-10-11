## 1. API refresh-session rotation

- [x] 1.1 Extend the auth repository contract and SQLAlchemy implementation with an atomic conditional refresh-token-hash replacement.
- [x] 1.2 Update the refresh use case to persist the successor hash and reject replayed or raced refresh tokens.
- [x] 1.3 Add service-level regression coverage proving the successor refresh token works and the previous token is rejected.

## 2. Frontend auth contract alignment

- [x] 2.1 Remove the stale required `companyId` field from NextAuth declarations and auth callback fixtures/assertions.
- [x] 2.2 Persist refreshed tokens in the streaming BFF response cookie, matching the existing non-streaming proxy behavior.
- [x] 2.3 Run targeted auth tests and type/lint checks, then verify the relevant API checks and OpenSpec validation.
