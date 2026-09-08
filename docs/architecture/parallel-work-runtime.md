# Parallel Work runtime

## Authority

### Mission authority

- **PW-004 / PW-005:** GlassHive is the durable mission authority. Core stores only account
  preference, trusted origin/delivery relations, a bounded roster projection, and presentation
  state.
- **PW-006:** No second mission authority or competing public work API is allowed.

### Single authority

- **PW-003:** Provider-native children remain internal to one root and never become another public
  Main, scheduler, registry, or mailbox.

### Idempotency

- **PW-068 / PW-069 / PWK-038:** Core issues a tool-occurrence-scoped `effectOccurrenceRef` before
  each durable effect. Exact replay reuses that reference and result; changed payload under the same
  reference fails closed. Multiple effects in one turn get distinct references rather than sharing
  one turn-wide ordinal slot.

## Admission and execution

### Scheduler

- **PW-085 / PW-087:** One persisted scheduler admits bounded work across every execution path;
  provider-native shortcuts cannot bypass it. Interactive work, approvals, exact controls, and
  callbacks outrank ordinary background work, account fairness applies, and queued capacity is
  rechecked centrally rather than through per-run retry timers.

### Lifecycle

- **PW-029 / PW-030 / PW-031 / HARD-009 / PW-045:** One schema owns public work states. Only completed, failed, and
  cancelled are terminal; work is `running` only after the leased runtime invocation starts.
  Canonical lifecycle state, not a UI favorite flag, is authoritative.

### Attempts

- **PW-032:** Attempts are immutable; retries do not rewrite the original start history.

### Isolation

- **PW-083:** Mutating work receives isolated workspace, runtime home, temporary state, logs, and
  process group. Safe read-only sharing is explicit; concurrent mutation is isolated or serialized.

### Process control

- **PW-084:** Stop addresses the exact process instance and tree so reused process identifiers cannot
  affect unrelated work.

### Configuration defaults

- **PW-086 / PW-088:** Capacity and resource guards are configuration defaults owned by
  `config.schema.yaml` and the existing runtime policy. They cannot consume the interactive lane;
  changing a default requires measurement at its owning seam.

## Context and controls

### Delegation decision

- **PW-015 / PW-017:** Main chooses answer, exact-work control, new mission, follow-up, or one needed
  target question in normal inference. Runtime never classifies this choice from complaint phrases
  or keywords.

### Dynamic context

- **PW-105:** Build one provider-independent ephemeral Active Work context before Main dispatch,
  fetch roster without serially blocking the turn, and map it through every Main provider adapter.
- **PW-106:** Bound and prioritize the context, provide overflow/list access, inject it only when
  relevant, and give Voice a compact urgent summary until more is requested. The current 16 KiB
  bound is configurable, not product law.
- **PW-107:** Dynamic work context is ephemeral conversation metadata, excluded from persisted chat
  and static authority fingerprints, and placed after the cacheable static prompt prefix.

### Host projection

- **PW-104:** Core combines the authoritative GlassHive roster only with trusted origin and delivery
  state from one owner-scoped relation.

### Roster

- **PW-019:** Roster entries use opaque work references; raw worker, provider, project, or session
  identifiers are never authority.

### Main tools

- **PW-103:** Main gets one list tool and one exact-work action tool. Provider diagnostics stay
  operator-only.

### Controls

- **PW-037:** Warm or provider-native Steer resume is allowed only under the same authority envelope.

### Control conflicts

- **HARD-022:** A stale, invalid, or conflicting control returns one definitive typed conflict; the
  API schema owns the transport mapping.

## Truth and recovery

### Provider health

- **PW-079 / HARD-006:** Capacity and provider cooldown are authoritative and centrally rechecked. Delivery
  timing uses presentation commit time, not a general update timestamp.

### Native children

- **PW-089 / PW-090:** Root state remains controllable when child telemetry is absent. Known live
  children settle before terminal presentation; unknown state is shown as degraded after a bounded
  configured reconciliation interval, never invented. A valid deliverable may appear early without
  falsely marking the mission terminal; 120 seconds remains only the current configurable default.
- **PW-091:** Stop controls the root process tree. Child controls require stable provider identity,
  and children cannot create peer mission roots through the durable mission API.

### Active Work projection

- **PW-102:** Active Work is an owner-scoped projection of mission, attempt, callback, delivery, and
  artifact truth with fresh, stale, or unavailable state, valid actions, overflow, and retention
  until failure resolution or delivery acknowledgement.

### Service API

- **PW-101:** One owner-scoped authenticated service interface owns delegation, Active Work listing
  and detail, and exact-work actions; route shapes stay in its API schema.

### Handoff envelope

- **HARD-011:** Handoff uses authoritative health and sends only the goal, constraints, required
  capabilities, and necessary evidence—never raw private chat or host identity.

### Trace

- **HARD-012:** One redacted immutable trace links source, authorization, admission, execution,
  callback, delivery, and artifact; unknown or contradictory critical evidence blocks readiness.

Product behavior is owned by [Parallel Work](../requirements_and_learnings/capabilities/parallel-work.md)
and [GlassHive](../requirements_and_learnings/capabilities/glasshive.md).
