# rag-console-app-shell Specification

## Purpose
TBD - created by archiving change rag-console-ui. Update Purpose after archive.
## Requirements
### Requirement: Console routes require an authenticated session

The console UI SHALL render all post-login work areas under a `/console/*` route segment
protected by a session guard. A request to any `/console/*` route without a valid NextAuth
session MUST redirect to `/login` with a callback URL preserving the intended destination. The
guard MUST NOT accept client-supplied tenant or role claims to bypass the redirect.

#### Scenario: Unauthenticated user opens a console route

- **WHEN** an unauthenticated user navigates to any `/console/*` route
- **THEN** the UI redirects to `/login` with a `callbackUrl` set to the requested route and
  does not render any console content

#### Scenario: Authenticated user is redirected from login

- **WHEN** an authenticated user completes the existing credentials login
- **THEN** the UI redirects to the console root and the shared console layout renders with the
  session available to all child routes

### Requirement: The console shell provides unified navigation to all work areas

The console UI SHALL provide a shared layout with persistent navigation that links to the four
work areas: ingestion, retrieval, settings, and an overview. Navigation MUST reflect the
active route and MUST NOT expose links to backend-internal or admin-only surfaces that the
caller is not authorized to use.

#### Scenario: User navigates between work areas

- **WHEN** an authenticated user selects a navigation entry
- **THEN** the active entry is visually marked and the corresponding route renders inside the
  shared layout without a full page reload

### Requirement: The shell handles session expiry gracefully

The console UI SHALL detect a terminal authentication failure from the BFF proxy (a final 401
after refresh attempts) and redirect the user to `/login` with a callback URL, surfacing a
non-blocking notice that the session expired. It MUST NOT silently drop the in-flight task or
leave the user on a stale console view.

#### Scenario: Access token can no longer be refreshed

- **WHEN** a console request receives a terminal 401 from the proxy after refresh failure
- **THEN** the UI redirects to `/login` with a callback URL and shows a session-expired notice
  without displaying protected data

### Requirement: All backend calls go through the BFF proxy with no client-side secrets

The console UI SHALL reach the backend exclusively through the existing `/api/proxy/[...path]`
BFF route. It MUST NOT call `apps/api` directly from the browser, MUST NOT read or store backend
secrets, API keys, or provider credentials, and MUST rely on the proxy for token injection and
refresh.

#### Scenario: A hook makes a RAG request

- **WHEN** a console hook issues a RAG ingestion or query request
- **THEN** the request is sent to `/api/proxy/rag/...` and no access token, refresh token, or
  provider secret is present in client-side code or browser storage

### Requirement: The console UI is clean, responsive, and accessible

The console UI SHALL use the existing Tailwind-based design system and component library to
present a simple, clean, and elegant interface. It MUST be responsive across desktop and
tablet widths, MUST use semantic landmarks and keyboard-operable navigation, and MUST follow
the repo Biome rules (no `any`, no `console.*`, `const`, double quotes, no semicolons).

#### Scenario: User uses keyboard to navigate the shell

- **WHEN** an authenticated user tabs through the console navigation
- **THEN** focus moves through operable, visible focus indicators and the user can activate any
  navigation entry without a pointing device
