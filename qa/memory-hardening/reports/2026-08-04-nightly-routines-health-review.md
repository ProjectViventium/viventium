# 2026-08-04 Nightly Routines Health Review

Automation: `viventium-nightly-routines-qa`

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Audit local time | 2026-08-04 11:17-11:32 EDT |
| Audit UTC time | 2026-08-04 15:17-15:32Z |
| System timezone | America/Toronto; `date` reported EDT `-0400`; `/etc/localtime` resolved to America/Toronto |
| Automation fire truth | `automation.toml` has `BYHOUR=11;BYMINUTE=15` with no timezone field. The prompt says `11:15Z`, but this Desktop run was observed around 11:17 local / 15:17Z. Treat this as an observer timezone-label mismatch, not a Viventium product scheduler failure. |
| Generated runtime schedule | memory hardening `0 3 * * *`, timezone America/Toronto, provider `openai`, model `gpt-5.6-sol`, effort `xhigh`; Workbench nightly enabled with GlassHive host executor and Sol/xHigh route |
| LaunchAgent schedule | memory hardening label loaded with one `StartCalendarInterval`: Hour 3, Minute 0; no competing `StartInterval` observed |
| Workbench scheduled prompt | built-in `Subconscious Deep Thought` active, daily 03:00 America/Toronto, memory off, latest due `2026-08-04T07:00:00Z`, completed, next run `2026-08-05T07:00:00Z` |

## Due Windows

| Routine | Due local | Due UTC | Grace used | Audit judgment |
| --- | --- | --- | --- | --- |
| Memory hardening | 2026-08-04 03:00 EDT | 2026-08-04 07:00Z | 60 minutes | DUE |
| Transcript scan and maintenance inside hardener | 2026-08-04 03:00 EDT | 2026-08-04 07:00Z | 60 minutes | DUE |
| Transcript catch-up behavior | Only applicable after a missed/deferred occurrence | N/A today | N/A | NOT EXERCISED TODAY |
| Transcript RAG service health | supporting service check during audit | supporting service check during audit | N/A | CHECKED |
| Prompt Workbench nightly reflection | 2026-08-04 03:00 EDT | 2026-08-04 07:00Z | 60 minutes | DUE |
| Periphery risk-radar artifact from Workbench | expected after Workbench completion, by about 04:00 EDT | expected by about 08:00Z | Workbench completion plus artifact freshness | DUE |
| User-level account/provider routines | account-specific schedules | account-specific schedules | not part of built-in nightly contract | WATCH / ACCOUNT ACTION |

No built-in routine was still before its due time plus grace.

## Status Summary

| Lane | Status | Evidence |
| --- | --- | --- |
| Memory hardening scheduled execution | PASS | Latest trigger receipt fired at `2026-08-04T07:00:05.568Z`, finished at `2026-08-04T07:02:40.208Z`, exit 0, run `20260804T070008Z`, run status success. Requested and effective route matched OpenAI / `gpt-5.6-sol` / `xhigh`. |
| Memory LaunchAgent | PASS | Agent was installed and loaded, state not running after completion, last exit 0, one 03:00 local calendar trigger, no conflicting interval trigger, lifecycle receipt successful. |
| Memory hardener model/apply telemetry | PASS for execution; read-back not run | Latest summary reported one selected/applied user hash, one model attempt, zero failures/fallbacks, zero conflicts/rejections, 368 messages and 71 conversations in lookback, and prompt input below the configured cap. Changed-key evidence is hardener-summary evidence; this audit did not independently read back private memory contents. |
| Power and heat safety | PASS-AUDIT-SAMPLE | Audit-time state was AC power, battery full, and no current thermal/performance warning. No hardener power-budget skip or override was observed. This is audit-time evidence, not a direct overnight power sensor trace. |
| Transcript scan and scheduled maintenance | PASS-SCHEDULED-HEALTHY-NOOP | Hardener telemetry saw 39 files, 6 ignored by config, 33 unchanged, 0 pending, 0 summary failures, 0 skipped by cap, 0 chars fed to model, and 0 uploads/deletes. |
| Transcript catch-up | NOT EXERCISED TODAY | The built-in jobs fired on time; no missed-fire or catch-up branch was needed. |
| Vector/RAG telemetry | PASS-SERVICE with proof gap | RAG health returned `UP`. Hardener summary recorded 0 vector presence errors, but no vector-presence probe denominator was captured because no transcript vector work was pending. Browser transcript recall/source-card proof was not rerun and remains a separate recall-signoff gap. |
| Prompt Workbench nightly chain | PASS | Scheduler task was active and completed the 03:00 occurrence. The run row had rendered and variable hashes, a GlassHive run id, completion callback payload, status completed, and no error class. |
| GlassHive callback chain | PASS / WATCH | The Aug 4 worker.ready, run.queued, run.started, and run.completed callbacks all delivered on attempt 1. Nine historical dead-lettered callbacks remain old watch items; no current pending/delivering callback backlog was observed. |
| GlassHive queue health | WATCH / P2 OWNER NEEDED | Three GlassHive run rows remain queued from Jul 30. They do not implicate today's built-in run, but they can corrupt queue-depth signals and need an owning cleanup/reaper decision. |
| Workbench visible scheduled-run proof | PASS | Playwright opened the live Workbench, selected the built-in schedule, verified the Aug 4 completed run, Sol/xHigh provenance, complete evidence snapshot, fresh passed risk-radar artifact, reload then reselect persistence, memory off, and zero memory proposal refs. Current-run Playwright snapshots were deleted. |
| Periphery risk radar | PASS | Latest visible artifact was generated Aug 4 around 03:04 local, quality status passed, confidence high, severity medium, 7/7 sources resolved, markdown present, stale-after Aug 5, and memory proposal refs were zero. Static periphery evals are harness-contract support, not a substitute for this live artifact proof. |
| User-level provider/account schedules | WATCH / ACCOUNT ACTION / FORWARD RISK | Separate active rows showed Telegram mapping/account setup failures and connection-refused/provider reconnect failures. They are not today's built-in nightly failure, but they use adjacent provider/account infrastructure and should be repaired before relying on later scheduled user/account work. |
| Runtime/source drift | CONTEXT | Overnight evidence exercised the installed/running runtime checkout, while focused tests and evals ran from this public workspace, which already had broad unrelated dirty changes. The tests support source health for this workspace; receipts/DB/browser evidence prove the 03:00 artifact. |
| Desktop observer timing | WATCH-LABEL-MISMATCH | The config has an 11:15 recurrence with no timezone field and the run happened at about 11:17 local. The prompt's `11:15Z` wording appears mislabeled for this Desktop environment. This did not affect product judgment. |

## Evidence Checked

- Automation memory was read before judgment.
- Automation config was inspected for the observer recurrence.
- Generated runtime env was inspected for memory hardening, Workbench, Scheduler, GlassHive, RAG, transcript, and scheduled-agent model settings. Secret values and local paths are omitted here.
- Memory hardening status JSON, latest trigger receipt, lifecycle receipt, LaunchAgent plist shape, launchd state, hardener summary, and redacted log tails were inspected.
- Scheduler health endpoint, Scheduler SQLite task/run rows, Workbench status, and GlassHive run/callback rows were inspected.
- RAG health endpoint returned `UP`.
- `bin/viventium status` was checked; it reported Viventium ready, Scheduler running, Nightly Reflection active, Memory Hardening healthy, Prompt Workbench running, and account setup warnings.
- Workbench was exercised in a real browser with Playwright through the live local UI, including detail-state and reload/reselect checks.
- Owning QA case rows were updated for memory hardening, transcript service health, Workbench, scheduling, and periphery nightly insight evidence.
- Git state was reviewed only to avoid trampling unrelated changes; no source changes were made beyond this public-safe QA report and case-row updates.

## Commands And Results

| Check | Result |
| --- | --- |
| `bin/viventium memory-harden status --json` | PASS; latest scheduled trigger and run succeeded with matching provider/model/effort tuple |
| memory LaunchAgent plist and launchd state | PASS; single 03:00 calendar trigger, loaded, last exit 0 |
| `bin/viventium prompt-workbench status --json` | PASS; Workbench running, stack-managed |
| Scheduler `/health` | PASS; public-safe runtime identity hash present |
| RAG `/health` | PASS; `UP` |
| Scheduler DB latest built-in Workbench task/run audit | PASS |
| GlassHive DB latest built-in run/callback audit | PASS for current run; old dead letters and queued rows are WATCH |
| Playwright Workbench UI open/select/reload/reselect | PASS for completed Aug 4 scheduled run and artifact; generated snapshots deleted |
| `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi python -m pytest tests/release/test_memory_hardening_contract.py tests/release/test_config_compiler.py tests/release/test_prompt_workbench.py tests/release/test_scheduled_glasshive_prompts.py tests/release/test_periphery_eval_harness.py -q` | 341 passed, 27 skipped |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | 12 passed, 0 failed |
| `python3 qa/periphery-nightly-insights/scripts/run-periphery-evals.py` | 6 passed, 0 failed, non-live harness mode |
| `bin/viventium memory-dedupe --dry-run --json` | PASS; duplicate groups/docs/deletes all 0, indexesCreated false. Corpus denominator was not captured, so this is a dry-run cleanliness signal, not full dedupe proof. |
| `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi python -m pytest tests/release/test_qa_results_public_safety.py -q` | 1 passed |
| focused public-safety grep over updated report/case files | PASS; no local absolute paths, account identifiers, launch tokens, secret values, or private runtime state were found in the new evidence text |

Earlier isolated pytest attempts failed only because the temporary Python environment lacked `pytest`, `PyYAML`, `pydantic`, `croniter`, or `fastapi`; the final isolated dependency set passed.

## Claude Review

ClaudeViv was not available on PATH. Local Claude CLI `2.1.220` completed a review-only, tool-disabled second opinion with sanitized evidence and no file changes.

Claude confirmed that the built-in memory, Workbench, callback, and periphery lanes are genuinely proven for Aug 4. It recommended tightening these points, which this report incorporates:

- power evidence is audit-time spot evidence, not direct overnight thermal/power trace;
- transcript catch-up was not exercised today because the scheduled runs fired on time;
- vector presence and dedupe zero counts lack denominator evidence;
- source-tree tests should not be described as proof of the installed 03:00 artifact;
- old queued GlassHive rows deserve an owner even though they do not downgrade today's built-in run;
- the observer issue is likely a timezone-label mismatch, not true cadence drift;
- user/account provider issues remain separate from today's built-in pass, but are forward risk.

## Full-View Checklist

| Requirement | Result |
| --- | --- |
| Timezone and due-window truth anchored before classification | PASS |
| Built-in hardener judged from LaunchAgent receipt plus summary, not Workbench evidence | PASS |
| Workbench judged from scheduled prompt -> filled variables -> GlassHive -> callback -> scheduler ledger -> visible Workbench | PASS |
| Power and thermal safety checked without override | PASS-AUDIT-SAMPLE |
| Transcript/RAG degraded evidence separated from browser recall proof | PASS |
| Catch-up behavior separated from on-time scheduled execution | PASS |
| Public/private boundaries preserved in repo evidence | PASS |
| Real browser user path checked for Workbench | PASS |
| No manual model-backed apply, transcript ingest, catch-up, rebuild, repair, or owner memory mutation was started by the audit | PASS |
| Review-only second opinion completed | PASS |

## Next Actions

1. Add an owner or cleanup/reaper decision for the three old queued GlassHive rows so queue-depth signals stay truthful.
2. Fix or document the automation prompt/config timezone mismatch: config recurs at 11:15 with no timezone field, while prompt says 11:15Z.
3. Repair separate user/account scheduled-row issues before relying on those user-level routines: Telegram mapping/account setup, provider reconnect, and connection-refused rows.
4. Capture vector-presence probe counts and dedupe scanned-document denominators in future status evidence.
5. Consider staggering memory hardening and Workbench nightly starts; both fired within one second of 07:00Z and both depend on high-effort OpenAI routing.
6. Run browser transcript recall/source-card proof only when transcript-recall release/signoff requires user-visible recall evidence.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
