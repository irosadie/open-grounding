## 1. Backend SSE progress

- [x] 1.1 Add an optional progress callback to the RAG query service and emit bounded planning, retrieval, generation, and validation milestones.
- [x] 1.2 Forward progress callbacks from the SSE route while the query runs, without releasing answer content before the existing final validation.
- [x] 1.3 Add API tests covering progress ordering, failure behavior, and unchanged validated answer deltas.

## 2. Query console rendering

- [x] 2.1 Parse and store `response.progress` events in the stream hook.
- [x] 2.2 Render the latest progress status while the query is in progress.
- [x] 2.3 Add frontend tests for progress parsing and state updates.

## 3. Contract and verification

- [x] 3.1 Update the OpenAPI streaming description and the relevant RAG specs.
- [x] 3.2 Run targeted API/web tests, type checks, lint, OpenAPI export, and OpenSpec validation.

## 4. Conversation continuity

- [x] 4.1 Generate or preserve the conversation ID before the first SSE progress event.
- [x] 4.2 Store the early conversation ID in the frontend stream hook for follow-up queries.
- [x] 4.3 Add regression coverage for the initial ID handoff and client retention.

## 5. Selectable response delivery

- [x] 5.1 Add a Stream checkbox to the Query console, defaulting to enabled, and pass the selected mode through the transaction hook.
- [x] 5.2 Support the blocking JSON response in the existing query hook state without changing the validated answer presentation.
- [x] 5.3 Add frontend/API regression coverage and update the Query console documentation.
