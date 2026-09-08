# Main Continuity QA Cases

The machine-readable case catalog is [`contract.v1.json`](contract.v1.json). The generated status
view is [`generated-coverage.md`](generated-coverage.md). These files are the single data source;
this page provides the standard QA-folder entry point without duplicating 46 mutable case rows.

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Required cases | Real surface | Supporting evidence | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MC-UC-001` | Receive configured Main schedule output, reply to that exact Telegram bubble, then ask a terse follow-up. | `MC-001`, `MC-002`, `MC-010`, `MC-011`, `MC-020` | Telegram Desktop, Workbench, scheduler | Delivery receipt, typed reply descriptor, accepted Main turn, provider replay decision | Main owns and explains its scheduled output; the terse follow-up stays on that objective. | `PARTIAL`, 2026-08-21 — a natural exact reply passed on repaired pre-final source and persisted after final restart; terse continuity remains pre-P0. No new Telegram generation ran after final activation. |
| `MC-UC-002` | Continue the same objective across Telegram and browser, use an internal specialist, and refresh. | `MC-040`, `MC-042`–`MC-046` | Telegram Desktop, browser, GlassHive | Structured content parts, provider topology, refresh DOM, shared visible-text projection | One final Main answer; specialist evidence stays internal; owned parts survive refresh. | `PARTIAL`, 2026-08-21 — final-source normal chat recovered offline FINAL without reload, showed one branch, and survived refresh; exact live lost-terminal/404, provider abort/tombstone, expanded details, and multi-agent final-source live proof remain open. |
| `MC-UC-003` | Send overlapping turns, corrections, and substantial independent work while Main stays available. | `MC-003`, `MC-007`, `MC-023` | Telegram Desktop, browser, Active Work | Accepted/reserved admission ledger, work receipts, callback and Active Work state | Every accepted turn commits once; durable work continues while Main answers the quick request. | NOT RUN — cataloged 2026-08-29 on the latest candidate; historical adjacent Parallel Work evidence is linked from the owning requirement. |
| `MC-UC-004` | Use long conversations through compaction, overflow, restart, provider fallback, and recall degradation. | `MC-005`–`MC-009`, `MC-017`–`MC-019`, `MC-025`–`MC-027`, `MC-037` | Browser, Telegram, GlassHive, recall/RAG | Context manifests, semantic compaction, usage calibration, fallback snapshot digest, recall health | Continuity stays bounded and coherent; degradation is truthful; retry is exact and limited. | `PARTIAL`, 2026-08-21 — bounded automation exists; forced live and real 100-plus-turn paths remain open. |
| `MC-UC-005` | Exercise unknown, deleted, foreign, group, multipart, retry, and crash-window Telegram provenance. | `MC-013`–`MC-016`, `MC-021`, `MC-022` | Telegram Desktop | Outbound message ledger, reply descriptor, scheduler delivery state, crash receipts | Known owners resolve; unknown owners say they cannot be verified; ambiguous sends are not duplicated. | `PARTIAL`, 2026-08-21 — final-source automation closes the group or anonymous owner-boundary defect; real unknown, deleted, foreign, group, multipart, retry, and crash paths remain open. |
| `MC-UC-006` | Prove the exact source, pin, built artifact, installed process, restart, and public/private boundary. | `MC-033`–`MC-035` | CLI, installed runtime, clean checkout | Nested commits, parent pins, artifact hashes, installed process identity, safety scan | A clean install runs the exact reviewed candidate and preserves private/public boundaries. | `PARTIAL`, 2026-08-21 — the exact dirty source and installed runtime are registered; clean nested commits, parent pins, build, install, and rollback remain open. |

## Compaction fidelity acceptance (`MC-008`)

Compare old and proposed source-owned compaction prompts on the exact configured Main primary and
fallback assignments. Include preserved paraphrases and changed permission, quantity, uncertainty,
attribution, pending work and corrections. Freeze the cases and expected review decisions before the
run; record label corrections without erasing earlier evidence. Requirement 49 owns human calibration.
Measure generation and review separately, plus automatic compaction frequency under short and large
turns. Tools, saved memory, recall and Feelings stay isolated for role evaluation; this is supporting
model evidence, separate from Main's delivered context and real browser/Telegram continuity.

Deterministic source tests must prove that an unreviewed or mismatched candidate cannot replace source,
that rejected/unavailable review preserves pending evidence, that whole paraphrases survive persistence,
that automatic batching carries all pending source intact before deferral, and that pressure,
interruption, concurrent corrections and restart preserve the source/lease boundary. Real delivery
must retain consequential conditions after compaction and after reload. An explicit context-budget
omission is a degraded result, not successful recall or a complete long-conversation result.

Original-source coverage must include a consequential condition after 5 KiB, an indivisible source
turn above 96 KiB, more than 64 pending turns during a provider outage, and a reviewed batch that
leaves later references untouched. Use actual native Message/Conversation records and the presentation
acceptance path. Verify full text and tool outcomes at claim and persisted reload; deletion, changed
text, changed owner/conversation/agent, and a superseding revision must prevent stale promotion.
Measure the source hydration queries and compaction calls, including the larger single-turn path.
Reference retention with a truthful budget failure is safe degradation, not successful semantic recall.


Projection and source lifecycle coverage must include a late duplicate after compaction, 131 later
acceptances and service reconstruction; deletion of the highest marker followed by epoch change
and an older first projection; both source locks under concurrent deletion; transaction rollback;
owner isolation; and hidden, non-forgeable projection markers. Delete one pending source, add eight
valid turns, compact and reload. A temporary missing record or read failure must preserve that source.
Deletion bookkeeping must preserve epoch freshness order and keep retirement floors out of model
context. These database checks support, but do not replace, the real long-conversation journey.

Cross-epoch persistence must prove all three races independently: edit after promotion hydration but
before CAS; epoch-A maintenance after epoch-B accepts a newer turn; and simultaneous first acceptance
in two epochs. Accept both concurrent turns once in one domain order. A correction on different
Message IDs must conflict with an old-prefix promotion. Test receipt-only system appends separately
from effective text/tool-result changes, including an already-promoted source.

Legacy cases must retain a higher pending/recent revision after the old 128-entry cache evicts it,
and after a lower deletion floor already exists. Reconcile the same immutable artifact independently
under two real epochs. Distinguish proven retired source from unproven missing source before model
assembly. Compare old/proposed prompts on that distinction; deterministic annotation alone is not
semantic proof. A large legacy record without within-record progress remains an open capacity gate.

Normal Main carrier coverage must use whole source beyond the turn-context limit, then a new
conversation and reload. Verify original Message IDs through the actual SDK and native admission,
not only the compactor. Include more than 128 visible messages, identical repeated text after pruning,
concurrent invoke/stream calls, same-ID edits, a reserved call that later fails, and protected source
that exceeds the real provider budget. Native identity belongs in one final request body manifest;
small authority headers must survive capability refresh. Request guards must remain local to Main's
run and leave background-agent configuration unchanged. Direct-provider serialization and exact
configured fallback behavior require their own evidence; a native adapter test does not close them.

## Native direct-turn restart recovery (`MC-036`)

Start a natural direct Main request, interrupt only the host API while its native run remains
alive, and let that exact native run finish. Restore the host, open the same conversation, and
verify one canonical answer with the original assistant ID, source parent, and origin. Reload
again. Trace one native invocation and no recovery model/fallback start. Repeat before native
dispatch, after native terminal state, after private host candidate preparation, after publication
commit, after actual Message save, and after final-event persistence but before delivery acknowledgement.

Repeat with Stop before admission and before publication; source edit/delete; explicit assistant
edit/delete; replaced stream incarnation; changed owner, agent access, or provider origin; failed
and cancelled native runs; and a completed record without an artifact. No stale or foreign answer
may appear. A post-commit source edit may retain only the exact accepted historical candidate.
A host graph tool call cannot become a Main answer. Expiry and unavailable authority must be
truthful, and an in-memory store must not claim restart durability.

Check browser and Telegram delivery with memory pending, partial, failed, and uncertain receipts.
An unacknowledged send must remain unacknowledged. Verify the existing 20-minute cleanup paths
retain an eligible native admission through its fixed 24-hour deadline, and test two host replicas
before claiming cross-replica final/memory ordering. These real-surface cases remain `NOT RUN`
for the September candidate until their exact source/build/runtime evidence is recorded.

## Release Test Traceability

- `tests/release/test_main_continuity_contract.py`
- `tests/release/test_qa_operating_contract.py`
- `tests/release/test_qa_results_public_safety.py`

## Release rule

Main continuity is not complete while any applicable real user path is `NOT RUN`, `PARTIAL`,
`BLOCKED`, or `FAIL`, or while the exact nested source/pin/build/install chain is unproved.

Supporting release regressions: `tests/release/test_queen_turn_diagnostics.py`. These automated checks do not replace the user-path acceptance above.
