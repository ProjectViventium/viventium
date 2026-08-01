<!-- qa-evidence-exempt: Synthetic isolated upgrade evidence; no installed or personal state was inspected. -->
# Post-Commit Mutation Inventory And Recovery QA

Date: 2026-07-24

## Outcome

Post-commit startup is now a durable upgrade phase rather than “the HTTP listener opened.” The
first-upgrade/current-session bridge derives one exact run ID from the committed transaction and
successor source, exports it through detached/full startup, and verifies an owner-only `0600`
receipt before acceptance. Upgrade health, API, and OAuth remain unavailable until required
startup mutators finish. Ordinary non-upgrade startup keeps its existing health behavior.

A previously stopped install stays stopped. Its bridge receipt remains `pending_first_start`; the
first later start inherits the same run/source identity. Foreground startup terminalizes after
health; detached/health-skipped startup arms a bounded after-health monitor. The finalizer rechecks
the exact protected LibreChat environment and helper configuration before terminal status. A crash
after API readiness leaves the bridge pending, and any terminalizer failure stops the owned runtime
instead of leaving an accepting API.

## Mutation Inventory

| Surface | Commit relationship | Durability / retry invariant | Evidence status |
| --- | --- | --- | --- |
| Parent/nested source and component pins | Outer transaction | Immutable ledger, exact rollback before commit | Covered by `CONT-010` |
| Canonical uploads relocation | Post-commit, writers stopped | Dedicated journal, no-follow copy/hash, idempotent forward recovery, one canonical authority | Covered |
| LibreChat role/access-role/category seed | Post-commit API start | Ordered idempotent writes; existing nonempty/custom state preserved; any stage failure leaves readiness unavailable and whole sequence retries | Covered with fault-after-stage tests and owning method tests |
| Mongoose/channel indexes | Post-commit API start | Strict index identity, in-place TTL `collMod`, resulting-option verification, no drop/delete, retry after later failure | Covered in unit and real disposable MongoDB |
| OAuth reconnect initialization | Post-commit API start | Strict upgrade mode propagates failure; retry occurs under the same run identity | Covered structurally/focused |
| Channel encrypted persistence and worker restore | Post-commit API start | Strict first restore propagates; index readiness is retryable; periodic ordinary recovery remains | Covered |
| Permission migration inspection and interface permissions | Post-commit API start | Awaited required stage; failure keeps receipt failed/unavailable and retries | Covered by startup contract |
| Stale cortex recovery | Post-commit API start | Awaited only for upgrade readiness; ordinary background behavior remains | Covered by startup contract |
| Generation runtime | Post-commit API start | Required before terminal readiness in single and clustered entrypoints | Covered, including clustered stage parity |
| Conversation search / Meilisearch | Post-commit derived state | Explicit `best-effort-derived-state`; rebuildable and never represented as required completed data | Covered/classified degraded |
| RAG PostgreSQL credential reconciliation | Post-commit sidecar start | Owner-only forward journal, exact mount/role/schema/corpus identity, pre/post corpus digest; retry/forward completion | Covered by its owning QA; not global rollback |
| Scheduling Cortex schema | Post-commit sidecar start | Explicit SQLite `BEGIN IMMEDIATE`; all DDL rolls back together; retry preserves task rows | Covered by interruption regression |
| Memory-hardening LaunchAgent | Post-commit host reconciliation | Exact plist/mode/loaded-state checkpoint and rollback | Covered by owning QA |
| macOS helper bundle/config/registration | Post-commit host reconciliation | Owner-only in-progress receipt and stage-bound forward recovery; protected config merge | Covered by owning QA |
| Telegram, voice, MCPs, GlassHive, prompt workbench, optional Docker sidecars | Post-commit configured start | Configured surface health gates and their owning identity/receipts; upgrade finalization does not claim them healthy from core listen alone | Covered by owning QA; full real-user parity remains open |

## Fault And Retry Evidence

- Exact support-floor shell matrix: running/stopped × healthy/corrupt successor helper passed in a
  disposable two-commit repository. The active outer-lock self-recovery regression is fixed by
  authenticating the exact quiesced receipt before generic interrupted-upgrade recovery.
- Focused LibreChat suite: 38 passed. It includes upgrade health/API/OAuth gating, same-run failure
  retry, POSIX ownership boundary checks, default-seed failure after each stage, channel strict
  restore, private receipt-mode drift refusal, TTL conflict refusal, and a real MongoDB interruption
  after `collMod` with preserved document and successful retry.
- Scheduling storage suite: 9 passed. The regression first proved SQLite DDL was not rollback
  atomic in legacy Python mode; explicit `BEGIN IMMEDIATE` now rolls back the first `ALTER`, and
  retry creates the complete schema with the synthetic task unchanged.
- The focused parent bridge, protected-state continuity, and runtime-order suites passed 110 tests.
  The seven broader upgrade/ordinary-start fixtures that initially exposed the new gate's missing
  no-receipt fast path and missing exact-receipt test setup also passed after correction.
- Focused bridge/order checks cover exact receipt wiring, stale/wrong/incomplete receipt refusal,
  terminalizer and readiness-timeout failure using the public owner-scoped stop path, health-skip
  monitor wiring, stopped first start, API-ready crash window, protected environment/helper recheck,
  and terminal persistence.
- Shell syntax, Python compilation, and Node syntax passed for the changed entrypoints.

## Exact Remaining Non-Atomic Boundaries

1. The parent/source commit still precedes default Mongo seed/index changes. These mutations are
   idempotent, protected-state preserving, receipt-gated, and retry-proven, but they do not have a
   global before-image that can roll the source commit and all data changes back together.
2. Gateway-link TTL conversion is an in-place MongoDB `collMod`. It preserves documents and is
   retry-proven, but has no inverse before-image. Failure after conversion converges forward.
3. RAG internal-role credential reconciliation is a forward journaled, corpus-invariant migration;
   it is not part of the parent source rollback transaction.
4. Derived Meilisearch data is rebuildable and explicitly degraded. It is not authoritative user
   state and does not block API readiness, but release wording must not call the search index
   synchronized merely because core startup completed.
5. External provider reconnects and optional sidecar dependency/image/model warming can fail after
   source commit. Configured health/identity gates and owning receipts make the failure visible and
   retryable; they cannot provide one atomic rollback across third-party services.

Scheduler DDL, uploads, memory LaunchAgent, and helper installation are not in this remaining list:
each now has an explicit local transaction or durable forward-recovery receipt with fault evidence.

## Limits

This protected lane did not read or mutate personal App Support, MongoDB, conversations, schedules,
prompts, credentials, helper installation, or the live runtime. It did not perform a real installed
Native/Docker upgrade, browser login/chat/upload persistence, provider OAuth reconnect, Telegram
delivery, audible voice, or shipped/pinned/installed artifact parity. Those user paths remain
`PARTIAL`; this report does not call the universal upgrade release fully finished.
