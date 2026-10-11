## MODIFIED Requirements

### Requirement: The shell handles session expiry gracefully
The console UI SHALL detect a terminal authentication failure from the BFF proxy (a final 401
after refresh attempts) and redirect the user to `/login` with a callback URL, surfacing a
non-blocking notice that the session expired. It MUST NOT silently drop the in-flight task or
leave the user on a stale console view. A refresh that succeeds MUST leave the session usable
for subsequent access-token refreshes.

#### Scenario: Access token can no longer be refreshed

- **WHEN** a console request receives a terminal 401 from the proxy after refresh failure
- **THEN** the UI redirects to `/login` with a callback URL and shows a session-expired notice
  without displaying protected data

#### Scenario: Access token refresh succeeds

- **WHEN** the BFF exchanges a valid refresh token for a new token pair
- **THEN** the session cookie is updated with that pair and a later refresh using the new refresh token remains valid

