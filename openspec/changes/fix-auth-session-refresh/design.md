## Context

The refresh use case validates the token hash stored in `auth_sessions`, creates a successor pair, and currently returns without updating that stored hash. The BFF then stores the successor token in its encrypted session cookie, so the API and browser disagree about which refresh token is current. See `proposal.md` and the two delta specs for the externally visible behavior.

## Goals / Non-Goals

**Goals:**

- Make refresh-token rotation persistent and replay-safe without changing required token claims or endpoint paths.
- Keep the update inside the existing domain-use-case and repository boundaries.
- Remove the stale frontend `companyId` requirement and keep auth tests aligned with the API response.
- Make the streaming BFF write the same refreshed session cookie as the regular proxy route.

**Non-Goals:**

- No change to access-token expiry, refresh-token lifetime, JWT secrets, or cookie lifetime.
- No migration or redesign of the authentication model.
- No changes to unrelated console or streaming behavior.

## Decisions

- Add a repository operation that conditionally replaces the session hash only when it still matches the hash being exchanged. This makes the old token unusable after a successful rotation and prevents a concurrent/replayed exchange from overwriting the current token.
- Perform the conditional replacement inside the repository's existing transaction context. A failed replacement raises the same invalid-token domain error used for all other refresh failures.
- Keep the session identifier and expiry unchanged. The refresh operation rotates the credential, not the logical login session.
- Add a unique `jti` to each refresh JWT. The existing claims remain intact, while the identifier prevents two tokens minted in the same clock second from being byte-for-byte identical.
- Reuse the existing cookie encoding settings in the streaming route. The stream response itself remains an SSE response; only its `Set-Cookie` side effect is added when a refresh occurred.
- Remove `companyId` from the NextAuth module augmentation and auth test fixtures because the backend DTO has no such field. No frontend workaround will synthesize a value.

## Risks / Trade-offs

- [Risk] A user with an already stale browser session must sign in once more. → The current login flow remains unchanged, and the fix prevents the stale-session loop from recurring after the next successful sign-in.
- [Risk] Two simultaneous refresh requests can race. → The conditional hash replacement allows only the request holding the current hash to win; the loser receives an invalid-token response and the BFF can use its existing terminal-session handling.

## Migration Plan

Deploy the API and web changes together. Existing `auth_sessions` rows continue to work because their current hash is accepted once and replaced on the first successful refresh. No data migration is required. If rollback is needed, revert the application code; already-rotated sessions may require a fresh login under the old behavior.
