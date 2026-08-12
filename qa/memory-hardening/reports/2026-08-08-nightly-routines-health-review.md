# 2026-08-08 Nightly Routines Health Review

Public-safe read-only audit of the Viventium overnight routines after the 03:00 local maintenance
window. Evidence below uses sanitized paths, withheld private runtime ids, hashes, counts, and
status classes only. Raw prompts, transcript text, memory values, account identifiers, callback
payloads, artifact bodies, and local absolute paths are intentionally omitted.

## Result

Overall: **FAIL / DEGRADED**.

The memory-hardening lane recovered and passed the configured OpenAI route, and the periphery
snapshot prerequisite that failed on Aug 6 is now healthy. The due Prompt Workbench nightly still
failed after it reached GlassHive, produced no paired `risk_radar` `.md`/`.json` deliverables, and
left the latest risk-radar artifact stale.

## Timing Anchor

| Item | Evidence |
| --- | --- |
| Audit anchor | 2026-08-08 11:16:09 EDT / 2026-08-08T15:16:09Z |
| Report closeout check | 2026-08-08 11:37:53 EDT / 2026-08-08T15:37:53Z |
| System timezone | America/Toronto from `/etc/localtime` and `date` |
| Automation fire time | Prompt-provided previous fire: 2026-08-07T15:15:46.396Z; current observer began around 2026-08-08T15:16Z |
| Observer cadence note | Automation prompt says 11:15Z, but local automation config has no timezone field and observed fires are around 11:15 local / 15:15Z. This is an observer cadence mismatch, not a product scheduler failure. |
| Generated runtime timezone/config | `VIVENTIUM_DEFAULT_TIMEZONE=America/Toronto`; memory hardening `0 3 * * *`; Workbench seed nightly enabled; Scheduler/GlassHive/RAG enabled |
| LaunchAgent calendar | single loaded `StartCalendarInterval` at Hour 3, Minute 0 |
| Workbench scheduled-prompt timezone/next run | America/Toronto; next due after today's terminal run is 2026-08-09T07:00:00Z |

## Due Windows

| Routine | Due local | Due UTC | Completion / lateness rule used | Actual observed | Judgment |
| --- | --- | --- | --- | --- | --- |
| Memory hardening LaunchAgent | 2026-08-08 03:00 EDT | 2026-08-08T07:00:00Z | direct LaunchAgent receipt; audit allowed >30m observer grace | fired 03:00:00 local; finished 03:00:51 local, exit 0 | PASS |
| Transcript ingest/catch-up inside hardener | 2026-08-08 03:00 EDT | 2026-08-08T07:00:00Z | same scheduled hardener run | scan completed with zero pending work | PASS-SCHEDULED-NOOP |
| Workbench built-in nightly reflection | 2026-08-08 03:00 EDT | 2026-08-08T07:00:00Z | scheduler misfire grace default 900s; built-in catch-up max 43,200s | started 03:00:17 local; terminal failed 03:00:50 local | FAIL/P1 |
| Periphery risk-radar artifact | produced by terminal Workbench run | after 2026-08-08T07:00:00Z | same terminal Workbench chain; no separate post-failure retry is owed | no Aug 8 sidecar pair; latest artifact stale since Aug 7 | FAIL/P1, same root event |
| RAG/vector support | supporting service, not a nightly generation due time | N/A | health-only support check | service health UP | PASS-SERVICE / QA proof gap for browser recall |

No audited routine was before its due time plus grace. The Workbench failure is therefore not an
audit-timing false positive.

## Status By Lane

| Lane | Status | Evidence |
| --- | --- | --- |
| Memory hardening schedule | PASS | Latest public-safe launchd receipt fired at 2026-08-08T07:00:00Z, linked the latest run, finished with exit 0, and had no stale lock. |
| Memory hardening execution | PASS-ROUTE-PROVEN / WATCH-DURATION | Latest run succeeded with requested and effective OpenAI `gpt-5.6-sol` / `xhigh`, `execution_mismatch=false`, one successful OpenAI advisory probe, no fallback, no provider/runtime/vector errors, and zero memory-key changes. The whole run completed in about 49s, materially shorter than recent applied runs, so duration remains an anomaly to watch rather than a failure by itself. |
| Transcript maintenance | PASS-SCHEDULED-NOOP | Scheduled scan saw 39 transcript files, 6 ignored by config, 33 unchanged, 0 pending, 0 summary failures, 0 cap skips, 0 vector presence errors, and 0 vector uploads/deletes/deferred. |
| Power/thermal | PASS | Machine was on AC power, charged, with no thermal/performance warning and no current power-budget skip. No override flags were used. |
| Prompt Workbench scheduled prompt | FAIL/P1 | Built-in due row had rendered-variable and variable-snapshot hashes, reached GlassHive, then terminally failed with `glasshive_evidence_check_failed`. Parent task, child run, API state, and visible Workbench state agreed on failure and advanced the next run to Aug 9. |
| GlassHive worker deliverable | FAIL/P1, root event | The failed worker row had zero output text and a completion-compliance diagnostic for missing required artifact types. The worker run directory contained only runtime logs, stdin, and exit-code files; no `.md` or `.json` deliverables were present. Private runtime ids are withheld. |
| Scheduler/callback substrate | PASS-DELIVERED-FAILURE / WATCH | Queue/start/fail callbacks for today's failed Workbench run delivered once with no active callback backlog. Dead-letter count remained historical: 9 total, newest updated July 11, and 0 since the Aug 6 anchor. Three old queued GlassHive rows remain stale cleanup/watch items. |
| Periphery snapshot | PASS-REPAIRED | Snapshot generation for the Aug 8 Workbench run was complete, with no missing prerequisites, 120 selected/included conversations, 9 memories, 578 messages, 735 source refs, 10 recent runs, and 11 reasoning lenses. This closes the Aug 6 degraded-snapshot streak. |
| Periphery risk-radar artifact | FAIL/P1, same root event | No Aug 8 `risk_radar` sidecar pair exists. Latest sidecar pair is from Aug 6, stale after Aug 7, with quality `warning` for reason `stale` only. This means the Aug 6 quality-gate repair is partly confirmed for stale classification, but no fresh artifact was generated today. |
| RAG/vector support | PASS-SERVICE / PROOF-GAP-RECALL | RAG health endpoint returned UP and hardener vector telemetry was clean. Browser recall/source-card proof was not rerun and remains a QA proof gap, not a documented overnight-run failure. |
| Prompt Workbench sidecar availability | WATCH | Workbench was running for status/API/browser evidence during the audit. A later read-only probe found the Workbench port stopped and CLI status reported stopped; the audit did not restart it. This happened after the 03:00 terminal failure and is tracked as sidecar supervision watch, not the root cause of the nightly failure. |
| User-level scheduled prompts | WATCH / ACCOUNT ACTION | Separate user-level schedules showed connected-account reconnect errors. Those rows do not block the built-in nightly contract unless they affect the built-in schedule. |
| Observer automation | WATCH | The Desktop automation cadence appears local-time rather than the prompt's stated UTC intent. Today's audit still ran long after all 03:00 routines were due. |

## Evidence Checked

- Automation memory and current local/UTC/timezone evidence.
- Generated runtime env and installed config summaries.
- Active memory-hardening LaunchAgent plist and `launchctl` state.
- Memory-hardening schedule trigger receipt, latest summary, redacted run log, status JSON, selected-user/eligibility counts, model/provider/fallback telemetry, transcript telemetry, and vector telemetry.
- Power and thermal state via macOS read-only status commands.
- Scheduler health endpoint, Scheduler SQLite definition/run/task rows, Workbench schedule API/browser state, GlassHive health, GlassHive run/callback rows, and RAG health endpoint.
- Private periphery artifact metadata and file presence; artifact bodies were not copied.
- Git/worktree drift was noted but not repaired; the worktree was already broadly dirty before this report.

One read-only Workbench metadata API call refreshed the private periphery `_index.json` timestamp as
part of the product's current GET path. Artifact freshness was judged from artifact `generatedAt`
and `staleAfter`, not the audit-time index timestamp.

## Commands And Results

| Check | Result |
| --- | --- |
| `bin/viventium memory-harden status --json` | PASS; healthy latest receipt/run; no execution mismatch |
| LaunchAgent plist + `launchctl print` | PASS; one 03:00 local trigger, loaded, last exit 0 |
| Scheduler/GlassHive/RAG health probes | PASS for Scheduler, GlassHive, and RAG at main audit time |
| Workbench status/API/browser probe | PASS during main audit; later stopped sidecar WATCH |
| Scheduler and GlassHive SQLite read-only queries | PASS for truthful terminal failure and callback delivery; Workbench run itself FAIL |
| Playwright CLI Workbench inspection | PASS for visible active built-in schedule, timezone, next due, memory off, and complete snapshot manifest |
| Focused release suite | 197 passed, 23 skipped |
| Meeting transcript evals | 12 passed, 0 failed |
| Periphery eval harness | 6 passed, 0 failed, live mode off |
| `bin/viventium memory-dedupe --dry-run --json` | 0 duplicate groups/docs/deletions |

Temporary Playwright snapshots from the Workbench session were removed because they contained
private visible UI state.

## Repairs Confirmed

- Memory hardening route mismatch from the prior audit is repaired for Aug 8: requested and
  effective route matched OpenAI `gpt-5.6-sol` / `xhigh`.
- Periphery snapshot prerequisites are repaired for Aug 8: the snapshot is complete with nonzero
  conversations, memories, messages, and source refs.
- Periphery quality now marks the stale Aug 6 artifact as `warning` with reason `stale`; the prior
  degraded-snapshot quality issue is no longer reproduced by today's complete snapshot, but today's
  artifact generation failed before quality could be evaluated.

## Stale / Skipped / Failed / Partial Items

- **Failed:** built-in Prompt Workbench nightly/periphery artifact generation. Single root event:
  GlassHive completion compliance failed and produced no required `.md`/`.json` deliverables.
- **Stale:** latest risk-radar artifact is Aug 6 and stale after Aug 7; next automatic attempt is
  2026-08-09T07:00:00Z. Scheduler catch-up handles late firing, not post-failure auto-retry for an
  evidence-check failure.
- **Proof gap:** browser recall/source-card proof not rerun.
- **Observer gap:** no public QA report exists for the Aug 7 automation fire, so the Aug 7
  `provider_quota_exhausted` Workbench failure remains unclassified in `qa/`.
- **Watch:** both overnight model-backed paths ended unusually quickly compared with prior
  successful analytical runs; shared route degradation is not proven, but should be investigated
  with provider/attempt duration telemetry.
- **Watch:** Workbench sidecar stopped after main audit evidence collection.
- **Watch:** three old queued GlassHive rows and nine historical dead-letter callbacks remain old
  cleanup items; no fresh dead-letter delta was observed since the Aug 6 anchor.

## Claude Review

ClaudeViv was not available as a separate callable helper in this environment, so local Claude CLI
was used in review-only mode with edit and shell tools disallowed. Claude agreed with the overall
FAIL/DEGRADED verdict, memory hardening as not PARTIAL, Workbench as FAIL/P1 after due+grace, and
periphery as failed. It required these report corrections, which were incorporated:

- withhold GlassHive runtime ids from public QA;
- replace the invented 60-minute Workbench grace with scheduler misfire and catch-up thresholds;
- treat Workbench and periphery as one root event, not two independent P1 root causes;
- inspect whether deliverables existed in the worker run directory;
- use dead-letter delta evidence rather than absolute count alone;
- record the missing Aug 7 public report gap;
- include the duration anomaly and next automatic attempt.

Unresolved risks from the review: the exact provider/worker reason for the no-deliverable GlassHive
turn is not isolated, and the very short memory-hardening/GlassHive durations could indicate a
shared model-route or worker-runtime degradation even though the current ledgers record different
terminal classes.

## Next Actions

1. Repair the Workbench/GlassHive evidence-contract failure path so the built-in nightly either
   writes a valid no-result `risk_radar` `.md`/`.json` pair or records a more specific worker/runtime
   failure before the artifact contract check.
2. Investigate the unusually short Aug 8 model-backed runs with provider attempt duration telemetry,
   especially after the Aug 7 quota failure.
3. Decide whether to add an explicit retry/recovery path for retryable evidence-check failures, or
   document that the stale artifact remains until the next nightly attempt.
4. Write or explicitly waive the missing Aug 7 public QA report/classification.
5. Clean or retire the three old queued GlassHive rows and keep dead-letter delta checks in the
   nightly audit contract.
6. Inspect why Prompt Workbench was stopped at audit end and whether stack supervision should
   restart it without a manual action.
7. Re-run browser recall/source-card proof before any release-readiness claim involving recall/RAG.
