# 2026-08-06 Nightly Routines Health Review

Status: **PARTIAL / DEGRADED**.

The Aug 6 built-in Workbench nightly chain recovered and completed. The macOS memory-maintenance
LaunchAgent also fired on time and exited `0`, but the configured OpenAI `gpt-5.6-sol` route was not
used for the real hardening proposal. Periphery produced a fresh risk-radar artifact, but its
evidence snapshot was degraded for the second consecutive night and the artifact quality gate still
reported `passed`, so the periphery insight lane is a product QA failure, not a clean pass.

This report is public-safe. It omits local absolute paths, account identifiers, tokens, raw prompts,
private memories, transcripts, callback payloads, worker output, and private artifact text.

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Audit anchor local time | 2026-08-06 11:17:30 EDT |
| Report write local time | 2026-08-06 11:34:23 EDT |
| Report write UTC time | 2026-08-06T15:34:23Z |
| System timezone | America/Toronto, from `/etc/localtime` |
| Automation fire time | Last-run prompt says 2026-08-05T15:16:09.655Z; current observer run was active around 2026-08-06 11:17 EDT / 15:17Z |
| Automation RRULE | Daily `BYHOUR=11;BYMINUTE=15` with no timezone field in the local Desktop config |
| Observer timing note | The prompt says 11:15Z, but the local RRULE behaved as 11:15 local / 15:15Z. This is observer wording drift, not product scheduler failure. |
| Generated memory schedule | Enabled, `0 3 * * *`, timezone America/Toronto, preferred OpenAI `gpt-5.6-sol`, effort `xhigh` |
| LaunchAgent interval | Single `StartCalendarInterval` at Hour `3`, Minute `0`; direct wrapper command; no competing interval trigger observed |
| Workbench built-in schedule | Active daily 03:00 America/Toronto; next run 2026-08-07T07:00:00Z after the Aug 6 completion |

## Due Windows

| Routine | Due local | Due UTC | Grace | Timing classification |
| --- | ---: | ---: | ---: | --- |
| Memory hardening / maintenance | 2026-08-06 03:00 EDT | 2026-08-06T07:00:00Z | 60 min | DUE; audit after grace |
| Transcript ingest / catch-up inside hardener | 2026-08-06 03:00 EDT | 2026-08-06T07:00:00Z | 60 min | DUE; audit after grace |
| Prompt Workbench nightly reflection | 2026-08-06 03:00 EDT | 2026-08-06T07:00:00Z | 60 min | DUE; audit after grace |
| Periphery risk-radar artifact | by ~2026-08-06 04:00 EDT or Workbench completion + grace | by ~2026-08-06T08:00:00Z | 60 min | DUE; audit after grace |
| RAG service health | Supporting audit check | Supporting audit check | n/a | Not a scheduled due item |
| User-level connected-account schedules | Separate user/account action lane | Separate user/account action lane | n/a | Out of built-in nightly contract |

No built-in overnight routine was `NOT DUE`. The observer was late enough to judge every built-in
due window without repeating the June 4 false-failure pattern.

## Results

| Lane | Status | Evidence |
| --- | --- | --- |
| Memory LaunchAgent trigger receipt | PASS | Receipt fired at 2026-08-06T07:00:06Z, finished 2026-08-06T07:09:44Z, exit `0`, linked run `20260806T070330Z`, no lock held at audit. |
| Memory hardener execution | PASS-EXECUTION / FAIL-ROUTE | Run `20260806T070330Z` succeeded and applied selected user changes, but the real proposal used Anthropic `claude-opus-5` / `xhigh`; status reported `execution_mismatch`, provider/model mismatch, and `healthy=false`. |
| Memory preferred route proof | FAIL/P1 | The OpenAI `gpt-5.6-sol` candidate timed out only during the 30s advisory probe. The real model telemetry recorded one real attempt and it was Anthropic, so the configured 30-minute OpenAI route was never proven. |
| Transcript maintenance | PASS-SCHEDULED-NOOP | Transcript telemetry showed files seen `39`, ignored `6`, unchanged `33`, pending `0`, summary failures `0`, vector presence errors `0`, vector uploads/deletes/deferred `0`. |
| Prompt Workbench nightly reflection | PASS | Aug 6 due row started 2026-08-06T07:00:38Z, completed 2026-08-06T07:04:31Z, had rendered and variable snapshot hashes, GlassHive run id, callback payload, and visible Workbench completion. |
| Scheduler delivery ledger | PASS for built-in run / WATCH substrate | Scheduler child and parent rows agree with the completed Workbench run. Callback outbox had no pending/delivering rows, no stale delivering rows, and no fresh dead-letter delta since the Aug 5 audit. Three old GlassHive queued rows remain stale watch items. |
| GlassHive run/callback | PASS-DELIVERY / PROOF-GAP-ROUTE | GlassHive run completed with non-empty output hash and zero error text. `run.queued`, `run.started`, and `run.completed` callbacks delivered on first attempt. The runtime row did not expose effective provider/model provenance. |
| Periphery risk radar | FAIL/P1 | Fresh artifact existed and had schema-valid sidecar/markdown with quality `passed`, but its source snapshot was degraded with missing Mongo/user-selector evidence, zero conversations, zero memories, and zero messages for a second night. |
| Periphery quality gate | FAIL/P2 | The artifact quality summary did not downgrade for `snapshot.status=degraded` / missing prerequisites, allowing `passed` to mask an empty conversation/memory corpus. |
| RAG service | PASS-SERVICE / PROOF-GAP-RECALL | RAG health returned `UP`; browser recall/source-card proof was not rerun and remains a release-signoff proof gap, not a built-in nightly failure. |
| Power/thermal gate | PASS | Machine was on AC power, battery charged, no thermal/performance warning, and no power-budget skip was recorded. |
| User-level provider schedules | WATCH / ACCOUNT ACTION | Separate user-level rows still showed account/provider reconnect work. They did not block the built-in Workbench nightly contract. |
| Automation memory | FAIL-OBSERVER | Automation memory lacked the Aug 5 entry despite an Aug 5 report; this observer write gap degrades the next-run baseline and is being repaired by this run's memory update. |

## Evidence Checked

- Automation memory was read first.
- Generated runtime env was inspected for memory hardening, transcript ingest, Workbench,
  Scheduler/GlassHive, RAG, provider/model, and route settings. Secret values and local paths are
  omitted here.
- LaunchAgent plist and `launchctl print` state were inspected for direct wrapper command, single
  `StartCalendarInterval`, loaded/not-running state, and last exit code.
- Memory hardening status, schedule trigger receipt, latest run summary, redacted run log, model
  probe attempts, real model attempt telemetry, selected-user counts, transcript telemetry, vector
  telemetry, and lock state were inspected.
- Prompt Workbench API, Scheduler health, Scheduler SQLite parent/child rows, GlassHive health,
  GlassHive run/callback rows, and the visible Workbench schedule detail were inspected.
- Periphery snapshot model/manifest/full files and Workbench artifact API were inspected for
  snapshot status, missing-prerequisite state, source counts, artifact metadata, claim counts, and
  content-array counts. The index was regenerated on demand during the audit at 2026-08-06T15:19Z,
  after the initial time anchor.
- RAG `/health`, memory dedupe dry-run, power/thermal state, and git worktree state were checked.
- Existing worktree state was already dirty; this audit did not modify product code or runtime data.

## Commands Run

| Command | Result |
| --- | --- |
| `uv run --with pytest --with pyyaml --with pydantic --with fastapi --with croniter python -m pytest tests/release/test_default_nightly_routines.py tests/release/test_memory_hardening_contract.py tests/release/test_prompt_workbench.py tests/release/test_scheduling_mcp_supervision.py tests/release/test_periphery_eval_harness.py tests/release/test_rag_api_override_contract.py tests/release/test_qa_results_public_safety.py -q` | 195 passed, 23 skipped |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | 12 passed, 0 failed |
| `python3 qa/periphery-nightly-insights/scripts/run-periphery-evals.py` | 6 passed, 0 failed; non-live harness |
| `bin/viventium memory-dedupe --dry-run --json` | Duplicate groups/docs/deletes all `0` for memory entries and keys |
| Playwright CLI against Prompt Workbench | Visible Aug 6 completed run, historical Aug 5 failure, degraded evidence snapshot, fresh risk-radar artifact, and Aug 7 next run confirmed. Temporary private snapshots were deleted. |
| `uv run --with pytest python -m pytest tests/release/test_qa_results_public_safety.py -q` after writing this report and case updates | 1 passed |
| `git diff --check` for this report and touched QA case files | Clean |

## Claude Review

ClaudeViv was not available on this machine, so local Claude CLI was used review-only with a sanitized
evidence packet and read-only tools. Claude confirmed the Workbench chain, memory trigger receipt,
power state, and RAG checks, but challenged three provisional classifications:

- Memory route proof must be `FAIL/P1`, because the 30s probe is advisory and the real OpenAI
  `gpt-5.6-sol` route was not attempted/proven.
- Periphery must be stricter than partial, because Aug 5 and Aug 6 both had degraded snapshots and
  the quality gate ignores missing-prerequisite state.
- Scheduler callback substrate needed delta evidence; follow-up DB checks found no fresh
  dead-letter delta or active callback backlog, but did confirm stale queued GlassHive rows.

These challenges were incorporated into the statuses above.

## Requirement Checklist

- Timing truth anchored before judging: PASS.
- Due windows built in local and UTC with grace: PASS.
- Memory hardening judged from LaunchAgent receipt plus run summary, not Workbench: PASS.
- Workbench judged from scheduled prompt -> variables -> GlassHive -> callback -> Scheduler ledger
  -> visible Workbench: PASS.
- Power/thermal safety checked without overrides: PASS.
- Product failure separated from QA proof gap: PASS.
- Public/private boundary preserved in this report: PASS.
- Real-browser Workbench QA run: PASS.
- Claude review-only second opinion: PASS via local Claude fallback.

## Next Actions

1. Repair the memory hardener route policy so a successful scheduled apply proves the configured
   OpenAI `gpt-5.6-sol` route with the full unattended timeout, or fails truthfully instead of
   reordering to fallback after a short probe.
2. Fix the Workbench periphery snapshot access/user-resolution path. Scope it as a Workbench
   snapshot Mongo/user-selector issue, not a global Mongo outage; the hardener successfully read
   memory minutes later.
3. Update the periphery artifact quality gate so a degraded snapshot or missing prerequisite forces
   at least a warning/failure reason.
4. Clean up or explicitly retire the three stale July GlassHive queued rows.
5. Correct the automation prompt/cadence wording from `11:15Z` to the observed local-time RRULE, or
   change the RRULE if UTC fire time is truly required.
6. Keep browser recall/source-card proof visible as a release-signoff gap until it is rerun.
