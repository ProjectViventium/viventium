# Nightly Failure Prevention Repair - 2026-07-11
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Scope

This public-safe report records the structural fixes following a failed Workbench nightly run,
loader reconciliation churn, stale recurring scheduler state, and false-green/degraded local RAG
recovery. Raw prompts, conversations, account identifiers, paths, logs, DB rows, and secrets remain
in private local state.

## Timing And Outcome

The audit decision anchor was after both 03:00 configured-local-time routines and their grace windows.
The observer's configured fire is 11:15Z; Desktop invoked this audit around 15:17Z, so the observer
was late rather than early and no product failure was inferred from audit timing.

| Lane | Due in configured local time | Due in UTC | Grace used | Observed outcome |
| --- | --- | --- | --- | --- |
| Memory hardening and transcript ingest | 03:00 | 07:00Z | 30 minutes | Scheduled receipt 07:00:03Z; successful run finished 07:02:02Z |
| Workbench nightly reflection/periphery | 03:00 | 07:00Z | 45 minutes; 12-hour catch-up policy | Scheduled child started 07:00:19Z and failed before output; later manual runs completed |

No audited overnight routine was not due. Power evidence was AC, fully charged, with no thermal or
performance warning and no power-policy skip.

## Root Causes And Owning Fixes

| Lane | Causal chain | Owning fix | Current proof |
| --- | --- | --- | --- |
| Workbench / GlassHive | Managed Codex startup inherited unsupported ambient effort and Workbench dispatch could overwrite/ignore its persisted execution tuple | Workbench carries the config-driven profile/model/effort tuple; invalid legacy effort falls back only to configured policy; dispatch preserves supported values, ignores ambient user config, and fails closed when the tuple is absent; generic workers do not acquire an automation tuple | Workbench 98-pass suite, Scheduler 94-pass suite plus six recurrence subtests, GlassHive profile suite, completed manual callback chain, and browser-visible `xhigh -> xhigh` completion |
| Memory LaunchAgent | Reconciliation could unload/reload an already-correct agent and a proposed hourly recovery created a second model cadence | One `StartCalendarInterval`; parsed-plist idempotence; explicit-false-only uninstall; process-serialized install/uninstall; post-action verification and public-safe generation-hash receipts | 56 hardener tests; live loaded single-trigger plist; repeated live reconciliation `noop`; scheduled receipt/run success |
| Scheduling Cortex | Lateness used the oldest stale `next_run_at`, so today's eligible recurrence could be skipped; legacy default DB location could fork state | Resolve the latest eligible occurrence before grace/catch-up judgment; ledger that occurrence; use the canonical App Support DB by default while explicit env remains authoritative | Daily/weekday/weekly/monthly/interval/cron, DST, explicit-timezone, dispatch, and bootstrap tests; restarted scheduler health uses the canonical DB identity |
| Recall / RAG | FastAPI encoded DOWN as a tuple under HTTP 200; launcher trusted reachability; helpers could race Compose under different project names | Real 503 JSON; semantic `UP` probe; PGVector health ordering; behavioral interprocess lock; explicit compose-state classification; canonical `viventium-rag` project; fail-loud exit for phantom/foreign ownership | 11 RAG contract/behavior tests, shell syntax, Compose validation, live HTTP 200 `UP`, and healthy canonical RAG/PGVector containers |

## Design Alignment

- Separation of concerns remains intact: launchd owns memory maintenance; Scheduling Cortex owns
  Workbench recurrence; GlassHive owns worker execution; RAG/Compose owns vector readiness.
- Config choice wins: managed automation carries structured configured metadata, while ordinary
  workers remain general and config-driven. No model/provider remapping or prompt-text routing was
  added.
- Health is truthful: transport and semantic state must agree, Compose mutation is serialized, and
  a healthy port outside the canonical project is an ownership conflict.
- Schedule truth is occurrence- and timezone-aware. Calendar recurrences use their declared
  timezone; elapsed intervals retain their UTC anchor.
- No model-backed hardener, transcript ingest, vector rebuild, Docker reset, or private-state
  mutation was initiated by this QA repair.

## Runtime Evidence

- The scheduled hardener used one model attempt with no failure/fallback, one eligible user, 120
  messages from 16 conversations, no rejected operation, 31 transcript files seen, one pending,
  no cap skip, no summary/vector error, two transcript-vector uploads, and one inventory upload.
- A separate unscheduled helper run later completed on the newly generated model configuration.
  It is useful route evidence but is not substituted for the next scheduled proof.
- The 07:00 Workbench child reached GlassHive and returned a terminal failed callback. Scheduler
  ledger advancement and callback terminalization worked; the worker failed before output.
- Later manual Workbench children completed. The newest recorded requested and effective effort as
  `xhigh`; callback queues were empty, and a fresh browser session showed the completion, next
  03:00 run, persistence after reload, and zero console errors/warnings.
- RAG first reproduced the false-green legacy response. During a later controlled runtime rebuild
  it recovered under the canonical project and now returns semantic `UP`. A legacy vector-only
  `librechat` Compose project remains local state to retire on the next controlled Docker restart.
- GlassHive health showed zero queued/active runs and zero pending/delivering callbacks; historical
  dead-letter rows remain separate old evidence.

## Verification

- Memory hardening: `56 passed`.
- Prompt Workbench: `98 passed`.
- Scheduling Cortex dispatch/scheduler/bootstrap: `94 passed`, plus six recurrence subtests.
- RAG route/semantic/lock/state/resource contracts: `11 passed`.
- GlassHive profile runtime suite: pass.
- Python compilation, launcher `bash -n`, RAG `docker compose config --quiet`, and scoped
  `git diff --check`: pass.
- Playwright: schedule detail, configured model/effort, failed scheduled child, completed manual
  child, reload persistence, and zero fresh console errors/warnings; temporary private snapshots
  were removed.

## Independent Review

ClaudeViv review-only confirmed all four lanes are structural ownership fixes aligned with
`01_Key_Principles.md`, found no weakened requirement/test or complaint-shaped runtime heuristic,
and agreed the original problem was not removed as the solution. It initially flagged missing
non-daily/DST value tests, a direct LaunchAgent self-lock, behavioral RAG lock/state tests, and live
route proof. Those gaps were closed after the review. Its remaining valid release concerns are the
three dirty git roots/pin boundary, unrelated concurrent changes in shared files, legacy scheduler
DB migration semantics for unmanaged old installs, and the need for the next automatic occurrences.

## Remaining Gates

- The July 11 scheduled Workbench occurrence remains a historical FAIL. The next automatic 03:00
  occurrence must prove the repaired, restarted code without manual triggering.
- The next scheduled hardener must prove the newly generated model config; the successful scheduled
  run audited here used the prior generated model.
- Retire the legacy vector-only Compose project through a controlled supported restart; do not
  delete vector state ad hoc. Browser recall/source grounding remains a separate QA proof gap.
- Delayed live wake/catch-up remains a user-path proof for `SCHED-015`; all recurrence math is now
  covered synthetically.
- Changes remain local and uncommitted across the parent, LibreChat, and GlassHive git roots. Split
  unrelated concurrent work, commit nested roots independently, update parent pins/artifacts, and
  rerun installed-runtime QA before release-readiness is claimed.

## Traceability

- `MEMHARD-012`
- `PW-037`
- `SCHED-014`, `SCHED-015`
- `RAG-006`
