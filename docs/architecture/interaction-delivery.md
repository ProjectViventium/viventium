# Interaction delivery

This seam preserves one current answer without losing durable work.

## Source and supersession

### Source identity

- **CC-040:** Each external source event has a stable owner-and-conversation-scoped idempotency key.

### Atomic supersession

- **CC-039:** The authoritative active-turn lookup and one atomic cross-replica transition own
  supersession.

### Adapter contract

- **CC-041:** Adapters declare typed segment stability and supersession scope. Core never branches on
  adapter names.

## Commit boundary

- **CC-046:** Web commits after durable final persistence and successful stream completion;
  Telegram commits after successful final send or edit; Voice commits after completed playback.
  Previews and partial speech are not commits.

### Acknowledgement

- **CC-045:** Acknowledgement binds owner, adapter, logical turn, revision, disposition, and optional
  presentation reference.

## Durable delivery

### Origin binding

- **PW-070 / PW-072:** Trusted origin and one per-destination delivery record are persisted before
  dispatch. Disconnect before commit creates no mission; disconnect after commit reconciles exactly
  one result to its governed owner/origin continuation. If no valid target exists, state remains
  undelivered and creates one operator alert rather than inventing delivery.

### Idempotency

- **PW-071:** Effects, callbacks, delivery records, and terminal transitions use shared idempotency
  and compare-and-set terminality.
- Aggregate delivery state is reconciled only after the callback transaction commits, before its
  durable projection retry marker is cleared. Aborted attempts publish no delivery projection.

### Delivery states

- **PW-073 / PW-074:** Acceptance, persistence, enqueue, delivery, acknowledgement, failure, and
  intentional silence are distinct states.
- **HARD-007:** Completed insights have one owner-scoped durable delivery record and survive retry,
  replay, and restart.

### External dependencies

- **PW-075:** Work that needs external missions remains waiting until every required authoritative
  mission is terminal.

Presentation changes never cancel or repeat a committed effect, accepted mission, or durable
background task. Product behavior is owned by
[interaction delivery](../requirements_and_learnings/capabilities/interaction-delivery.md).
