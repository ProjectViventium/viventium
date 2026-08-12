# 2026-08-05 Nightly Routines Health Review

Automation: `viventium-nightly-routines-qa`

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Audit local time | 2026-08-05 11:16-11:32 EDT |
| Audit UTC time | 2026-08-05 15:16-15:32Z |
| System timezone | America/Toronto; `date` reported EDT `-0400`; `/etc/localtime` resolved to America/Toronto |
| Automation fire truth | `automation.toml` has `BYHOUR=11;BYMINUTE=15` with no timezone field. The prompt says `11:15Z`, but this Desktop run was observed around 11:16 local / 15:16Z. This is an observer cadence label mismatch, not a product scheduler timezone conversion. |
| Generated runtime schedule | memory hardening enabled, `0 3 * * *`, timezone America/Toronto, provider `openai`, model `gpt-5.6-sol`, effort `xhigh`; Workbench nightly enabled with GlassHive host executor and Sol/xHigh route |
| LaunchAgent schedule | memory hardening label loaded with one `StartCalendarInterval`: Hour 3, Minute 0; no competing `StartInterval` observed |
| Workbench scheduled prompt | built-in `Subconscious Deep Thought` active, daily 03:00 America/Toronto, memory off; Aug 5 due run failed, next run advanced to `2026-08-06T07:00:00Z` |

## Due Windows

| Routine | Due local | Due UTC | Grace used | Actual observed | Audit judgment |
| --- | --- | --- | --- | --- | --- |
| Memory hardening | 2026-08-05 03:00 EDT | 2026-08-05 07:00Z | 60 minutes | launchd receipt at 07:10 EDT / 11:10Z, failed exit `-9`, no run id | DUE / FAIL |
| Transcript scan and maintenance inside hardener | 2026-08-05 03:00 EDT | 2026-08-05 07:00Z | 60 minutes | no Aug 5 hardener summary; latest transcript index update remains Aug 4 | DUE / STALE |
| Transcript RAG service health | supporting service check during audit | supporting service check during audit | N/A | health endpoint returned `UP` | CHECKED / SERVICE UP |
| Prompt Workbench nightly reflection | 2026-08-05 03:00 EDT | 2026-08-05 07:00Z | 60 minutes | scheduler catch-up row at 07:11 EDT / 11:11Z, failed before GlassHive with connection refused | DUE / FAIL |
| Periphery risk-radar artifact from Workbench | expected after Workbench completion by about 04:00 EDT | expected by about 08:00Z | Workbench completion plus artifact freshness | no fresh Aug 5 artifact; visible Aug 5 evidence snapshot degraded | DUE / STALE |
| User-level account/provider routines | account-specific schedules | account-specific schedules | not part of built-in nightly contract | separate account/provider failures and future due times observed | WATCH / ACCOUNT ACTION |

No built-in routine was before its due time plus grace.

## Status Summary

| Lane | Status | Evidence |
| --- | --- | --- |
| Memory hardening scheduled execution | FAIL / P1 | Latest public-safe trigger receipt finalized `failed`, exit `-9`, with no run id. No Aug 5 run summary exists. Latest completed summary remains Aug 4. |
| Memory LaunchAgent schedule alignment | PASS-SCHEDULE / FAIL-EXECUTION | Installed and loaded LaunchAgent uses the direct wrapper with `--scheduled --trigger launchd`; generated schedule and StartCalendarInterval both resolve to 03:00 local. Execution failed after firing. |
| Memory hardener model/apply telemetry | FAIL-PROOF | Requested route in the failed receipt was OpenAI / `gpt-5.6-sol` / `xhigh`, but no effective provider/model tuple was produced for Aug 5 because no run summary was written. |
| Stale lock and efficiency marker | DEGRADED / WATCH | Status reported a held lock and `running` efficiency marker for the Aug 5 killed run. The recorded PID was not alive. Source inspection shows the next acquisition should clear a dead-PID lock and the five-minute efficiency window has elapsed, but the current status remains unhealthy until a successful run proves recovery. |
| Power and heat safety | PASS-AUDIT-SAMPLE / NO-SKIP | Audit-time state was AC power, battery full, and no current thermal/performance warning. No supported power-budget skip receipt was found. This is not a pass for the failed execution. |
| Transcript scan and scheduled maintenance | FAIL / STALE | The Aug 5 hardener did not reach transcript telemetry. Status still reported 56 processed transcript file records, and the main private index had 33 processed-content entries updated Aug 4. |
| Vector/RAG runtime | PASS-SERVICE with proof gap | RAG health returned `UP` and RAG/vector containers were healthy at audit time. There is no Aug 5 hardener vector-presence telemetry because the hardener failed before summary. Browser transcript recall/source-card proof was not rerun. |
| Prompt Workbench nightly chain | FAIL / P1 | Scheduler row for the Aug 5 03:00 occurrence had rendered and variable snapshot hashes, but failed immediately with connection refused, no GlassHive run id, no callback payload, and parent task status `error` / delivery outcome `failed`. Workbench advanced the next occurrence to Aug 6. |
| Workbench visible scheduled-run proof | FAIL-VISIBLE | Playwright opened the live Workbench detail. Recent Runs showed Aug 5 failed with connection refused and prior Aug 4-Aug 1 completions. The visible detail preserved Sol/xHigh provenance and memory-off state. |
| Periphery risk radar | FAIL / STALE / DEGRADED | No fresh Aug 5 risk-radar artifact was visible. Workbench showed an Aug 5 degraded evidence snapshot with a missing Mongo prerequisite at run time; the latest visible risk-radar artifact remained the Aug 4 artifact and was stale after Aug 5 03:04 local. |
| Scheduler service | PARTIAL / WATCH | Scheduling health endpoint was OK at audit time, but the built-in due run failed. Logs around the run window show stack supervision/backoff and restart activity overlapping the scheduled catch-up. |
| GlassHive callback and queue health | WATCH | GlassHive API health was OK with no active runs and no pending callback delivery. Three old queued host-worker rows and nine historical dead-lettered callbacks remained unchanged watch items from the prior audit, not a fresh Aug 5 delta. |
| User-level provider/account schedules | WATCH / ACCOUNT ACTION | Separate active schedule rows showed connected-account reconnect, Telegram mapping, and bad-request classes. These are not the built-in nightly contract failure, but they remain forward risk for user-level schedules. |
| Desktop observer timing | WATCH-LABEL-MISMATCH | The Desktop automation still appears to fire at 11:15 local despite the prompt saying 11:15Z. This did not make the Aug 5 audit early. |

## Evidence Checked

- Automation memory was read before judgment.
- Automation config was inspected for the observer recurrence.
- Generated runtime env was inspected for memory hardening, Workbench, Scheduler, GlassHive, RAG, transcript, and scheduled-agent model settings. Secret values and local paths are omitted here.
- Memory hardening status JSON, latest trigger receipt, lifecycle receipt, LaunchAgent plist shape, launchd state, hardener summary, stale lock files, and redacted log tails were inspected.
- Power and thermal state were checked with macOS power/thermal commands. No override or expensive model-backed work was started.
- Scheduler health endpoint, Scheduler SQLite task/run rows, Workbench status and browser UI, GlassHive health, run rows, callback rows, and current Mongo collection counts were inspected with private identifiers redacted.
- RAG health endpoint returned `UP`.
- Transcript state was inspected only through counts, timestamps, hashes, and status summaries.
- Workbench was exercised in a real browser with Playwright through the live local UI, including scheduled prompt detail state. Current-run screenshots/snapshots were closed and not kept as public evidence.
- Source inspection checked hardener lock recovery and cooldown semantics after Claude flagged stale-lock follow-up risk.
- Git state was reviewed only to avoid trampling unrelated changes; no product code was changed by this read-only audit.

## Commands And Results

| Check | Result |
| --- | --- |
| `bin/viventium memory-harden status --json` | FAIL-HEALTH; latest scheduled receipt failed exit `-9`, no run id, lock held, stale `running` efficiency marker, latest completed run Aug 4 |
| memory LaunchAgent plist and launchd state | PASS-SCHEDULE; single 03:00 calendar trigger, loaded, direct wrapper path, no competing interval trigger |
| generated runtime env review | PASS-CONFIG; memory and Workbench nightly schedules are configured for 03:00 America/Toronto with Sol/xHigh route |
| power and thermal checks | PASS-AUDIT-SAMPLE; AC power, charged battery, no thermal/performance warning, no supported skip receipt |
| Scheduler `/health` | PASS-CURRENT; service reports OK at audit time |
| RAG `/health` | PASS-CURRENT; `UP` |
| Scheduler DB latest built-in Workbench task/run audit | FAIL-RUN; Aug 5 due row failed with connection refused before GlassHive, no callback payload |
| GlassHive DB latest built-in run/callback audit | FAIL-PROOF for Aug 5 built-in run; no run/callback exists for today's failed dispatch; old queued/dead-letter rows unchanged watch |
| Mongo counts | PASS-CURRENT; current database was reachable with nonzero public-safe collection counts |
| Playwright Workbench UI open/select detail | FAIL-VISIBLE for Aug 5; visible recent run failed, prior runs completed, evidence snapshot degraded, no fresh artifact |
| `uv run --with pytest --with pyyaml --with pydantic --with fastapi --with croniter python -m pytest tests/release/test_default_nightly_routines.py tests/release/test_memory_hardening_contract.py tests/release/test_prompt_workbench.py tests/release/test_scheduling_mcp_supervision.py tests/release/test_periphery_eval_harness.py tests/release/test_rag_api_override_contract.py tests/release/test_qa_results_public_safety.py -q` | 195 passed, 23 skipped |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | 12 passed, 0 failed |
| `python3 qa/periphery-nightly-insights/scripts/run-periphery-evals.py` | 6 passed, 0 failed, non-live harness mode |

## Claude Review

ClaudeViv was not available as a structured helper in this environment. Local Claude CLI `2.1.220`
completed a review-only second opinion with sanitized evidence and no file changes.

Claude confirmed the core P1 calls: memory hardening is not a timezone/travel false alarm because
there is positive failed-receipt evidence; Workbench catch-up happened but failed on a dependency;
transcript and periphery failures are correctly derivative of the failed hardener and Workbench
runs; old GlassHive queued/dead-letter rows are unchanged watch items, not new Aug 5 degradation.

Claude also tightened the shared root-cause hypothesis: the Aug 5 hardener and Workbench catch-up
landed close together during a helper stack restart window, and the previous Aug 4 report had already
flagged schedule staggering as a forward-risk item. This report treats the wake/restart overlap as
the leading hypothesis, not as fully proven root cause.

Claude flagged one extra concern: a stale hardener lock could convert this into a second miss. The
follow-up source/read-only check found that dead-PID lock recovery should clear it on the next
acquisition and the efficiency cooldown has elapsed, so the current action is to repair and prove
recovery before the next window rather than calling tomorrow guaranteed blocked.

## Full-View Checklist

| Requirement | Result |
| --- | --- |
| Timezone and due-window truth anchored before classification | PASS |
| Audit avoids June 4 false early-fail pattern | PASS; all built-in routines were past due plus grace |
| Built-in hardener judged from LaunchAgent receipt plus summary, not Workbench evidence | PASS |
| Memory hardening separates schedule alignment from failed execution | PASS |
| Workbench judged from scheduled prompt -> filled variables -> GlassHive -> callback -> scheduler ledger -> visible Workbench | PASS; chain failed before GlassHive and that failure is preserved |
| Power and thermal safety checked without override | PASS-AUDIT-SAMPLE |
| Transcript/RAG service health separated from missing Aug 5 hardener vector telemetry | PASS |
| Public/private boundaries preserved in repo evidence | PASS |
| Real browser user path checked for Workbench | PASS |
| No manual model-backed apply, transcript ingest, catch-up, rebuild, repair, or owner memory mutation was started by the audit | PASS |
| Review-only second opinion completed | PASS |

## Next Actions

1. Repair/prove recovery for the Aug 5 memory-hardening state before the next 03:00 window: clear or let the next run clear the dead-PID lock, ensure the stale `running` marker is resolved, then verify the next receipt produces a run id and summary.
2. Add or adjust readiness/retry behavior so Workbench scheduled catch-up does not advance a built-in nightly occurrence to the next day after a pre-GlassHive connection-refused dependency race.
3. Revisit staggering of memory hardening and Workbench nightly schedules, since Aug 4 flagged same-window contention and Aug 5 failures overlapped a stack restart/wake recovery window.
4. Investigate why the Workbench evidence snapshot saw Mongo missing at run time while Mongo was healthy at audit time; this likely needs a startup readiness gate rather than a snapshot-quality workaround.
5. Keep the unchanged old GlassHive queued rows and historical dead-letter callbacks as P2 cleanup/watch items.
6. Repair separate user/account schedule issues before relying on user-level routines: connected-account reconnect, Telegram mapping, and bad-request rows.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
