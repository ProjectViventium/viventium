# 2026-07-31 Nightly Routines Health Review

Read-only audit of the Viventium overnight maintenance lanes after their scheduled
03:00 America/Toronto windows. Raw prompts, account identifiers, transcript text,
tokens, local private paths, and callback payload bodies are intentionally omitted.

## Timing Anchor

| Item | Evidence |
| --- | --- |
| Audit start | 2026-07-31 11:17:40 EDT / 2026-07-31T15:17:40Z |
| Report finalized | 2026-07-31 11:34:45 EDT / 2026-07-31T15:34:45Z |
| System timezone evidence | `date` reported EDT, UTC offset -04:00; admin-gated system timezone command was unavailable |
| Generated runtime timezone | `America/Toronto` |
| Codex observer fire time | Automation is documented as an 11:15Z observer; this Desktop run was observed around 15:17Z / 11:17 EDT |
| Generated memory schedule | Enabled, `0 3 * * *`, `America/Toronto`, OpenAI `gpt-5.6-sol`, `xhigh` |
| Active memory LaunchAgent | Missing/not loaded; no current `StartCalendarInterval` was available to inspect |
| Workbench schedule | Active daily 03:00 `America/Toronto`, next 2026-08-01T07:00:00Z |
| Recent observed memory run | Latest receipt/run remained 2026-07-30T07:00Z, success |
| Recent observed Workbench run | 2026-07-31T07:00:27Z to 2026-07-31T07:06:45Z, completed |

The observer fired after the product due windows and grace periods, so today's
missing memory hardener is a product scheduling failure, not a premature-audit
classification error.

## Due Windows

| Routine | Due local | Due UTC | Grace used | Audit relation | Judgment basis |
| --- | --- | --- | --- | --- | --- |
| Memory hardening LaunchAgent | 2026-07-31 03:00 EDT | 2026-07-31T07:00Z | 60 minutes | After due plus grace | Expected to have completed |
| Transcript ingest/catch-up within hardener | 2026-07-31 03:00 EDT | 2026-07-31T07:00Z | 60 minutes | After due plus grace | Expected with hardener |
| Workbench `Subconscious Deep Thought` | 2026-07-31 03:00 EDT | 2026-07-31T07:00Z | 60 minutes | After due plus grace | Expected to have completed |
| Periphery risk radar artifact | After Workbench run | After 2026-07-31T07:00Z | Workbench run completion | Completed before audit | Expected artifact was due |
| Later user-level schedules | Varies by user schedule | Varies | Schedule-specific | Some not built-in nightly | Watch only, outside built-in verdict |

No built-in overnight routine was classified `NOT DUE`.

## Routine Verdicts

| Lane | Status | Evidence |
| --- | --- | --- |
| Memory hardening | FAIL-MISSED | Status expected a 2026-07-31T07:00Z fire, but latest trigger receipt and run remained 2026-07-30T07:00Z. Schedule health reported unhealthy, missed expected window, LaunchAgent not installed/not loaded, and the launchd label was not present. |
| Transcript ingest/catch-up | FAIL-MISSED / PROOF BLOCKED | This lane is part of the missed hardener. Latest actual hardener evidence from 2026-07-30 scanned 39 files, ignored 6 sidecars, had 0 pending summaries, but recorded vector runtime unreachable. Current RAG API health was unreachable, so browser recall/vector proof remains blocked. |
| Saved-memory model/provider route | PASS-STALE | The latest actual run on 2026-07-30 used OpenAI `gpt-5.6-sol` with `xhigh`, one attempt, zero model failures, and zero fallback. It is stale because no 2026-07-31 run occurred. |
| Prompt Workbench nightly reflection | PASS | Scheduler parent row, child run, GlassHive run, callback outbox, and visible Workbench detail state all agreed on a completed 2026-07-31 run. |
| Periphery risk radar | PASS | Fresh schema-v2 sidecar and paired markdown existed for the 2026-07-31 Workbench run; quality passed, 7/7 source refs resolved, markdown present, stale-after set one week ahead, and memory proposal refs were 0. |
| Scheduler substrate | PARTIAL-DEGRADED | Live scheduler API was healthy and Workbench completed, but the scheduling LaunchAgent points to a missing generated wrapper and repeatedly exits 127. This is a restart/supervision defect. |
| GlassHive callback substrate | PASS-WATCH | Today's queued/started/completed callbacks delivered once with no pending or delivering callbacks. Historical dead letters and a small queued backlog remain watch items. |
| RAG/vector service | FAIL-SERVICE | Vector DB container was healthy, but the RAG API did not answer health checks. This blocks transcript recall/vector proof. |
| Power/thermal safety | PASS | Machine was on AC power, charging, and no thermal/performance warning was observed. No power or idle override was used. |
| User-level schedules | WATCH / OUT OF BUILT-IN SCOPE | Later user/account schedules showed mixed account-action delivery outcomes. They do not change the built-in overnight verdict unless they block the built-in contract. |

## Evidence Checked

- Project instructions, memory requirements, installer/compiler requirements, runtime QA map,
  Workbench, transcript memory, memory continuity, and periphery QA cases.
- Generated runtime configuration for memory hardening, Workbench, GlassHive, Scheduling MCP, and
  RAG endpoint values.
- Memory-hardening status JSON, schedule lifecycle state, schedule trigger receipts, latest summary
  telemetry, provider/model/fallback telemetry, transcript/vector telemetry, and power evidence.
- launchd state for the memory hardener and scheduling cortex labels.
- Scheduler DB rows for scheduled definitions, parent scheduled task state, and child scheduled
  prompt run state.
- GlassHive health, worker run ledger, and callback outbox summary.
- Workbench UI through Playwright: schedule detail, recent runs, evidence snapshot, and periphery
  artifact panel.
- RAG API health, vector DB container state, and current hardener vector telemetry.
- Git drift was inspected only to avoid disturbing unrelated local edits.

## Commands And Checks

| Check | Result |
| --- | --- |
| Focused release suite covering nightly defaults, memory hardening, compiler, Workbench, periphery, scheduling supervision, RAG override, and continuity audit | PASS, 344 passed, 23 skipped |
| Transcript eval harness | PASS, 12 passed, 0 failed |
| Periphery eval harness | PASS, 6 passed |
| QA results public-safety test after report/case edits | PASS, 1 passed |
| Memory dedupe dry-run | PASS, zero duplicate groups/docs/deletes |
| Playwright Workbench inspection | PASS for Workbench evidence; temporary current-run snapshots were removed |
| Local Claude review-only second opinion | BLOCKED; ClaudeViv unavailable and local Claude CLI hung twice until stopped |

## Failures And Repair Plan

1. Restore memory-hardening LaunchAgent installation/loading from the generated schedule and direct
   wrapper path, then verify a new lifecycle receipt and a forced-safe synthetic or next scheduled
   receipt without starting expensive model work during the audit.
2. Repair generated scheduling-cortex wrapper production or plist reconciliation. The live scheduler
   is healthy now, but launchd supervision would not survive restart because the wrapper is missing.
3. Restore RAG API service health and then rerun transcript vector presence and browser recall proof
   with synthetic or sanitized transcript evidence.
4. Keep the Workbench and periphery lanes marked PASS for today; they should not be reworked as part
   of the memory LaunchAgent repair unless new evidence ties them to the failure.
5. Retry the review-only Claude pass when the local CLI responds. No independent second opinion was
   completed in this run.

## Final Classification

Overall built-in nightly status is FAIL/PARTIAL: Workbench and periphery passed,
but the memory hardener and transcript sublane missed today's due window, RAG
API health blocks transcript recall proof, and scheduler launchd supervision is
degraded. This was not caused by an early observer run, timezone travel, DST, a
power-budget skip, or an intentionally empty eligible-user selection.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
