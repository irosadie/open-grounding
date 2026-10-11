## 1. Client streaming behavior

- [x] 1.1 Add a Unicode-safe FIFO answer queue with bounded typewriter ticks.
- [x] 1.2 Coordinate `response.completed` with queue draining and preserve the
  existing callback contract.
- [x] 1.3 Cancel timers and invalidate stale work on abort, replacement, and
  unmount.

## 2. Regression coverage

- [x] 2.1 Verify multiple deltas render in order as one exact final answer.
- [x] 2.2 Verify completion waits for queued answer content.
- [x] 2.3 Verify abort/replacement cleanup prevents stale answer content.

## 3. Verification

- [x] 3.1 Run the focused stream-hook tests, frontend typecheck, and lint.
- [x] 3.2 Validate the OpenSpec change and confirm no backend/database/logging
  files were changed.
