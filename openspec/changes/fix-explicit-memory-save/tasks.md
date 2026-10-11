## 1. Explicit memory eligibility

- [x] 1.1 Add a USER-message-only explicit save/remember intent predicate covering the
  supported Indonesian and English wording.
- [x] 1.2 Bypass the minimum-turn early exit only for explicit memory requests and update
  the decision contract without weakening privacy filters.
- [x] 1.3 Add regression tests for explicit short-turn requests, ordinary short-turn
  conversations, and prompt guidance.

## 2. Verification

- [x] 2.1 Run targeted memory summarizer tests.
- [x] 2.2 Run backend lint and type checks for the touched surface.
- [x] 2.3 Verify the existing API/worker contracts remain unchanged and no migration is
  required.
