<!-- qa-evidence-exempt: Historical pre-v2 forensic baseline retained without retroactively inventing evidence; the 2026-08-21 v2 report owns current acceptance. -->

# Main Continuity Current-Candidate Audit

**Date:** 2026-08-20
**Candidate:** local dirty source checkout; not a release artifact
**Overall:** `PARTIAL`

> This pre-activation audit is preserved as the forensic baseline. Approved containment, recovery,
> activation, the escaped scheduled-reply repair, and live QA are recorded in
> [the approved live repair report](2026-08-20-approved-live-repair-and-qa.md).

## User outcome

Viventium Main must feel like one bounded cognitive system across browser, Telegram, schedules,
fallback, and rapid turns. It must keep the immediate referent, preserve durable commitments, stay
within provider limits, retain native tools and workspaces, and state failures truthfully.

## Proven root cause

The reported incident was an AI continuity failure, not spoofing. A valid Telegram/Mongo parent
edge reached a provider path that had already pruned the preceding assistant turn. Mutable runtime
context changed the persistent native-session fingerprint, cumulative native usage was assigned to
a small visible turn, and the replacement worker treated the remaining small payload as a full
bootstrap. Telegram quote flattening then erased the message-author relation needed to explain a
reply accurately.

The current Main route resolves to the configured GlassHive Codex worker with its configured Claude
fallback. Route inheritance is therefore necessary but is not the missing cognitive-continuity
contract.

## Candidate changes proved by automated tests

- Provider time delivery, usage accounting, context protocol, native authority, and replay behavior
  are explicit independent capabilities.
- Stable authority is separated from mutable developer context. A real authority change rotates a
  native binding; mutable Feelings and runtime context do not.
- One request-local `MainContextSnapshotV1` digest is bound to primary and outer fallback attempts.
  The exact admitted instructions and encoded per-turn context are restored for the fallback.
- One owner-and-agent continuity domain now keeps at most three accepted interactive turns. New
  visible threads and Main schedules receive unseen turns from other threads; the current local
  thread outranks them. Scheduler/system envelopes can read this state but cannot write into it.
- GlassHive serial fallback uses the primary admitted instruction.
- Visible-conversation overlap queues on one canonical native worker instead of creating
  `:overlap:` sibling Mains.
- Replay is byte-bounded, keeps recent complete turns, and clips large tool payloads.
- Replay decisions are request-scoped. Only an accepted completion publishes the decision and its
  bounded Main-state advancement to the session; concurrent requests cannot overwrite each
  other's replay audit before acceptance.
- Telegram replies use a bounded typed descriptor and owner/chat-scoped outbound receipt lookup;
  quoted assistant text is no longer appended to the user-authored body.
- Scheduled Telegram delivery keeps the logical-turn receipt from both the chat-accept response
  and the SSE stream, then acknowledges all sent message IDs. Focused tests cover the actual
  dispatch-to-stream handoff instead of injecting the turn ID directly.
- TypeScript and Python read one closed scheduled-failure contract. Scheduler failure extraction
  preserves provider retryability, one-time attempts stop after three, recurring and one-time
  wording differ, the visible one-time retry timestamp matches the persisted transition, and
  repeated same-root notices coalesce.
- Exact structural schedule creation is atomic and idempotent. A replay returns the existing task;
  a meaningful prompt, rule, channel, executor, conversation, or metadata change remains distinct.
- File/photo/document replies carry the same typed reply provenance as text replies. Extracted
  quoted-document evidence stays in a bounded attachment descriptor instead of being dropped or
  appended to the new user text.
- Graph participants can read the owning Main capsule but cannot commit participant-only output
  into it. Only the continuity-owning Main agent can advance owner-Main state.
- Core chat falls back to an embedded conservative failure contract if the scheduler source file is
  absent from a partial artifact; a missing optional source file cannot stop all chat at require
  time.

Fresh test evidence:

| Surface | Result | Evidence scope |
| --- | --- | --- |
| LibreChat affected API suites | `PASS` | 439 tests |
| LibreChat durable logical-turn store | `PASS` | 40 tests |
| GlassHive runtime | `PASS` | Full runtime suite, exit 0 |
| Synthetic mixed continuity soak | `PASS` | 100 turns across five visible threads; stable bindings, bounded replay, scheduler-memory exclusion |
| Telegram bridge/bot package | `PASS` | 449 tests from the exact dirty candidate |
| Scheduling Cortex | `PASS` | 208 tests plus 10 subtests from the exact dirty candidate |
| Data-provider config | `PASS` | 64 tests |
| Public continuity registry | `PASS` | 2 contract tests and generated-view check |

These are supporting automated results. They do not replace the required real browser, Telegram,
restart, recall-recovery, and soak cases.

## Unresolved blockers and failed acceptance gates

1. The new durable owner-Main state is a bounded three-turn exact capsule. It is not the required
   validated semantic long-horizon state for asks, commitments, corrections, durable identifiers,
   recurrence outcomes, and tool pairs.
2. Replay still selects its base cursor from a session-global visible-message count. The persisted compaction is a
   bounded exact excerpt, not a validated semantic summary of asks, corrections, commitments,
   durable identifiers, recurrence outcomes, and tool pairs.
3. Overflow compact-and-retry and an exactly-once accepted logical-turn advancement CAS are not
   implemented.
4. The full developer-instruction layer is not yet governed by an explicit provider budget. The
   synthetic soak proves bounded replay for its payloads, not bounded arbitrary dynamic
   instructions.
5. The snapshot does not yet contain every required typed section, and Phase B does not yet prove
   exact snapshot-digest and capability-ceiling reuse.
6. Workbench terminal-state presentation for a one-time occurrence is not yet user-tested.
7. Per-run developer context is not fully restart-safe. A queued run can lose invocation-local
   authority and capability material across a process restart.
8. Main schedules now receive the bounded owner-Main capsule independent of `new|same`, but compact
   `RecurrenceStateV1` is not implemented.
9. Python and TypeScript now consume one closed failure contract, and copy derives from the
   computed transition. Release-chain generation/validation and automatic recurring-schedule
   pause remain pending.
10. Conversation Recall is degraded because the RAG API cannot authenticate to PostgreSQL. The
   vector database is healthy and must not be deleted or recreated.
11. Memory Hardening reports an execution mismatch that needs a separate owning-path repair.
12. The nested repositories contain large unrelated dirty change sets. Parent-pin equality identifies
   only committed `HEAD`, not the tested dirty source or installed code.
13. No real post-change Telegram provenance run, browser continuity run, process restart, recall
    recovery, or 100-turn mixed soak has passed.

## Read-only live drift evidence

- The live Main agent matches the tracked source-of-truth route. The local candidate proposes
  explicit Codex primary and Claude fallback worker-profile fields.
- Fourteen non-Main agents differ between live state and tracked source. The differences include
  instructions, tool arrays, model parameters, and workspace options. A broad agent sync is unsafe.
- The adjacent live LibreChat capability fields match their tracked source.
- Twelve schedules are active. Two exact structural duplicate groups have six and two members.
- The six-member group is an older daily morning-orientation schedule in a different timezone. The
  two-member group is the newer local-time morning-orientation schedule.
- The documented `compare --schedules` path does not compare schedules, its helper is absent, and
  the documented default database path does not point at the installed isolated scheduler state.

No agent was synced. No schedule was paused or deleted. No credential, database, service, installed
artifact, or user-facing runtime was changed. No Telegram message was sent.

## Specific recommendation

Use a per-visible-conversation native session plus one owner-and-agent-scoped durable continuity
capsule. Do not put all visible chats into one native provider session: that would mix thread-local
context and make native compaction, cancellation, and access boundaries harder to prove.

LibreChat remains the only admission owner. It projects one immutable snapshot containing the
current visible delta, the latest three complete local turns, the validated owner-Main semantic
capsule, explicit memory/recall health, Feelings, provenance, recurrence state, and capability
ceiling. Provider attempts consume the same snapshot. GlassHive executes it and advances only an
accepted logical-turn revision; it does not reconstruct Main context.

Delivery order:

1. Replace the remaining message-count cursor with exactly-once accepted-revision advancement.
2. Extend the bounded owner-Main capsule with validated semantic compaction, protected tool pairs,
   one overflow compact-and-retry, and restart-safe per-run context.
3. Add compact `RecurrenceStateV1` to Main schedules, independent of `new|same` visible-thread policy.
4. Keep the shared closed failure contract generated/validated as part of the release chain.
5. Repair Recall credentials through the owning config/restore path and diagnose Memory Hardening
   without deleting data.
6. Reconcile nested commits, parent pins, built artifacts, installed receipts, and running process
   identity; then restart and run the complete 37-case acceptance matrix and 100-turn soak.

Approval-gated live proposal:

- Keep the oldest member of the newer local-time morning-orientation duplicate group so its durable
  history remains canonical.
- Pause the other member of that group and all six older different-timezone duplicates. Do not
  delete any schedule or history.
- Do not sync the fourteen drifted non-Main agents as part of this continuity repair. Review each
  protected tool/model/instruction change separately.
- Repair the RAG credential in place only after a backup and an exact compiler/restore dry run.

## Acceptance status

The candidate is not release-ready. Automated contract slices pass, but every real-user case that
depends on the final owner-Main state, semantic compaction, restart recovery, installed artifact, or
live Telegram path remains `PARTIAL`, `FAIL`, or `NOT RUN` until a dated post-change report proves it.
