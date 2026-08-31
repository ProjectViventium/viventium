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

## Release Test Traceability

- `tests/release/test_main_continuity_contract.py`
- `tests/release/test_qa_operating_contract.py`
- `tests/release/test_qa_results_public_safety.py`

## Release rule

Main continuity is not complete while any applicable real user path is `NOT RUN`, `PARTIAL`,
`BLOCKED`, or `FAIL`, or while the exact nested source/pin/build/install chain is unproved.
