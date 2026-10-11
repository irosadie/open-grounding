## Context

The API already emits only validated answer text in `response.delta` events.
Those events can arrive in one network read, so transport chunking cannot be
used as a visual typing signal. The browser must buffer received deltas and
release them to React at a controlled cadence.

## Decisions

### Client-side queue, unchanged SSE contract

The stream hook keeps parsing the existing events. Each answer delta is split
into small Unicode-safe units and appended to a FIFO queue. A single timer
releases a bounded number of units per tick, preserving the exact event order
and answer text.

### Completion waits for visible content

`response.completed` metadata is stored as pending completion while the queue
drains. The hook changes to `completed` and invokes the completion callback only
after the last queued answer unit is rendered. Non-streaming JSON responses stay
immediate.

### Safe lifecycle handling

Starting a new request, aborting, and unmounting clear the queue, cancel the
timer, and invalidate the active stream generation. A late timer from an older
request cannot append content to a newer answer.

### No backend or persistence changes

The API remains responsible for producing validated deltas. This change does
not add token logging, database records, migrations, provider streaming, or
additional network endpoints.

## Risks / Mitigations

- **Risk:** A long answer could take too long to reveal. → Release a small
  bounded group per tick rather than one code point at a time.
- **Risk:** A stale timer could corrupt a follow-up answer. → Cancel timers and
  guard callbacks with a monotonically increasing request generation.
- **Risk:** Completion metadata could be shown before the answer is complete.
  → Delay completion state and callback until the queue is empty.
