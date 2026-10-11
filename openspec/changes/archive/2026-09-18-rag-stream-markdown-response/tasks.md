## 1. Streaming response contract

- [x] 1.1 Add a safe SSE text encoder for Markdown delta payloads.
- [x] 1.2 Emit validated answer deltas as raw Markdown in stream mode while
  preserving structured status and metadata events.
- [x] 1.3 Keep blocking JSON mode unchanged and document the dual contract.

## 2. Client rendering

- [x] 2.1 Parse structured SSE data and raw Markdown delta data.
- [x] 2.2 Render answer content with GFM Markdown for stream and blocking modes.
- [x] 2.3 Preserve typewriter queue, status updates, citations, and completion
  behavior.

## 3. Regression coverage

- [x] 3.1 Add API coverage for raw Markdown delta encoding and unchanged event
  ordering.
- [x] 3.2 Add frontend coverage for raw Markdown parsing and blocking JSON.
- [x] 3.3 Run backend/frontend tests, typechecks, lint, OpenSpec validation, and
  confirm no database or logging changes.
