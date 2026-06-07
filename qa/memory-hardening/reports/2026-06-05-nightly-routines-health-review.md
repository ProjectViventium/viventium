<!-- qa-evidence-exempt: recurring read-only nightly routine audit with timing-window table; keep standard report template for feature implementation reruns. -->

# 2026-06-05 Nightly Routines Health Review

## Summary

Overall status: **PARTIAL**, with the June 5 memory-hardening/model-backed transcript lane
**SKIPPED** by the power gate and the Workbench nightly chain **PASS with a significant
performance regression**.

This was a read-only overnight-routine audit anchored at `2026-06-05T13:07:26Z`
(`2026-06-05 09:07:26` America/Toronto). The previous automation run was supplied as
`2026-06-04T08:01:40.976Z`. No model-backed hardener apply, transcript ingest/catch-up, rebuild,
repair, background-agent run, runtime stop, Docker stop, data reset, or owner memory/chat mutation
was started by this audit. The only local state written by the audit was metadata-only continuity
audit output under App Support; no private content was copied into this report.

Public-safety rule for this report: raw operator account values, local App Support paths, transcript
filenames/text, private schedule prompts, prompt-workbench launch tokens, private detail paths,
callback payloads, browser snapshots, screenshots, and private Workbench content are omitted.
Evidence below uses sanitized counts, statuses, labels, hashes, and timestamps only.

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Current local time | `2026-06-05 09:07:26 EDT -0400` |
| Current UTC time | `2026-06-05 13:07:26 UTC` |
| System timezone | `/etc/localtime` resolves to `America/Toronto`; `TZ` was unset. `systemsetup -gettimezone` was admin-gated and not used as evidence. |
| Automation fire time used for judgment | `2026-06-05 09:07:26` America/Toronto / `2026-06-05T13:07:26Z` |
| Generated runtime timezone/config | Memory hardening enabled, schedule `0 3 * * *`, timezone `America/Toronto`, provider OpenAI/GPT-5.5 `xhigh`, dry-run-first on, transcript source configured, detailed-summary-only transcript RAG mode. |
| LaunchAgent schedule | Loaded `ai.viventium.memory-harden`, `StartCalendarInterval` hour `3`, minute `0`, last exit code `0`, not running during audit. |
| Workbench scheduled-prompt timezone/next run | Active Workbench task uses `03:00` `America/Los_Angeles`; after today's run, `next_run_at` is `2026-06-06T10:00:00Z`. |
| Recent observed memory-hardener runs | Successes at `2026-06-03T10:00:07Z` and `2026-06-04T10:00:05Z`; no `20260605*` run directory. |
| Recent observed Workbench runs | Completed due runs at `2026-06-03T10:00:00Z`, `2026-06-04T10:00:00Z`, and `2026-06-05T10:00:00Z`. |

## Due-Window Table

| Routine | Configured due window | Observed/effective due window | Grace used | Audit judgment |
| --- | --- | --- | --- | --- |
| Memory hardening scheduled apply | `2026-06-05 03:00` America/Toronto / `2026-06-05T07:00:00Z` | Recent successful/skip evidence lands at `2026-06-05 06:00` America/Toronto / `2026-06-05T10:00:00Z`, despite the loaded `03:00` LaunchAgent. | 45 minutes for wrapper start/skip evidence. Audit was after both windows. | **SKIPPED**: stderr mtime was `2026-06-05 06:00:00 EDT` with `on_battery_power`; no run directory was expected after a power-gate skip. Timing drift remains a separate finding. |
| Transcript ingest/catch-up inside hardener | Same as memory hardening | Same as memory hardening | Same as memory hardening | **SKIPPED** today because the hardener skipped before model/vector work. Latest successful baseline from June 4 had 0 pending and 0 vector errors. |
| Transcript summary/RAG artifact lifecycle | Same as memory hardening when transcript source is configured | Same as memory hardening | Same as memory hardening | **SKIPPED/PARTIAL** today: no fresh lifecycle work, but RAG health was `UP` and latest hardener vector telemetry was clean. Browser recall/vector-document proof was not rerun. |
| Workbench nightly reflection | `2026-06-05 03:00` America/Los_Angeles / `2026-06-05T10:00:00Z` | Started at `2026-06-05T10:00:09Z`, completed at `2026-06-05T13:07:10Z`. | 15 minutes for start, 4 hours for long GlassHive completion; anything over 60 minutes is a performance finding. | **PASS with significant performance regression**: full chain completed and visible Workbench state updated, but duration was 11,220 seconds versus recent 190-236 second baseline. |
| User-level provider reconnect schedules | `2026-06-05 08:00` America/Los_Angeles / `2026-06-05T15:00:00Z` | Not reached at audit time. | 30 minutes after due. | **NOT DUE / WAITING**; existing reconnect failures are account-action evidence, not today's built-in nightly failure. |
| Prompt benchmark / Workbench evals | No scheduled exact-model benchmark found for this overnight audit. | Manual fixture/test checks only. | N/A | **NOT DUE**; manual synthetic evals/tests passed. |

## Expected Vs Actual Routines

| Routine | Expected | Actual evidence | Status |
| --- | --- | --- | --- |
| Memory hardening | Scheduled wrapper should run without forcing expensive work on battery/thermal constraint. | Current machine was on battery; no thermal/performance warning was recorded. The hardener stderr file updated at `2026-06-05 06:00:00 EDT` and recorded `memory hardening skipped: on_battery_power`. No `20260605*` run directory was created. | **SKIPPED** |
| Transcript ingest/catch-up inside hardener | Scan configured transcript source and update bounded summary/vector lifecycle when hardener is allowed to run. | Today's hardener skipped before transcript/model/vector work. Latest status still shows 3 indexes / 47 files / 47 processed, and latest successful run saw 26 files, 0 pending, 0 skipped by cap, 0 requeued missing vectors, and 0 vector-presence errors. | **SKIPPED/PARTIAL** |
| Transcript summary/RAG artifacts | Keep detailed-summary-only RAG artifacts healthy and recallable. | Product-side lifecycle work was intentionally skipped because the hardener power-gated. RAG `/health` returned `UP`; unauthenticated `/metrics` returned 401 as expected; no browser recall/source-card answer or authenticated vector-document proof was rerun. | **SKIPPED product work / PARTIAL proof** |
| Workbench nightly reflection | Built-in `Subconscious Deep Thought` via Scheduler -> GlassHive -> callback -> Workbench. | Due at `2026-06-05T10:00:00Z`, started at `10:00:09Z`, completed at `13:07:10Z`; child run completed, parent task last status success/sent, GlassHive run completed, callback delivered, private detail pointer present. Playwright confirmed enabled schedule row, next Jun 6 local display, Jun 5 completed recent run, and Jun 5 memory-proposal file visible. | **PASS with significant performance regression** |
| Scheduler / GlassHive callback health | No fresh callback backlog or silently degraded delivery substrate. | Scheduler `/health` ok; GlassHive metrics had 0 queued/active runs, 0 pending/delivering callbacks, 2 historical dead-letter rows, and active callback max attempts 0. Latest `run.completed` callback delivered in 1 attempt. | **PASS** |
| Prompt Workbench evals | No scheduled exact-model benchmark expected unless due. | No due benchmark found. Manual transcript eval fixtures and focused release tests passed. | **NOT DUE / PASS manual checks** |
| Continuity / dedupe | Continuity audit available and no memory duplicate dry-run changes. | Continuity audit wrote metadata-only status under App Support; memory-dedupe dry-run reported 0 duplicate groups/docs/deletes for memory entries and keys. | **PASS/PARTIAL** |
| Status-bar/manual-ingest state | Helper should remain running; manual ingest should not be started by audit. | `bin/viventium status` showed macOS Status Bar Helper running and Transcript Ingest configured. This audit did not run manual ingest. | **PASS / NOT RUN** |

## Evidence Checked

### Power And Launch State

- Battery/power: current `pmset -g batt` reported battery power at 100% and discharging.
- Thermal/performance: `pmset -g therm` reported no recorded thermal, performance, or CPU power warning.
- LaunchAgent: one Viventium memory-hardener label was loaded in the GUI domain with hour `3`,
  minute `0`, direct wrapper invocation, App Support working directory, last exit code `0`, and not
  running during the audit.
- Skip evidence: hardener stderr file mtime was `2026-06-05 06:00:00 EDT`; latest matching lines
  included `memory hardening skipped: on_battery_power`.
- Run-state evidence: no `20260605*` run directory exists; latest run state remains
  `20260604T100005Z`.

### Memory Hardening

- Generated runtime config: hardening enabled, schedule `0 3 * * *`, timezone `America/Toronto`,
  dry-run-first on, OpenAI/GPT-5.5 `xhigh`, `launch_ready_only`, and one configured operator scope
  redacted from public evidence.
- Latest successful run: `20260604T100005Z`, mode `apply`, provider OpenAI, model GPT-5.5, status
  success, started `2026-06-04T10:00:05Z`, finished `2026-06-04T10:02:24Z`.
- Latest redacted telemetry: one model attempt, zero attempt failures, zero fallback, one selected
  user, 361 messages fed, 2 changed keys, 0 rejected operations, transcript pending 0, requeued
  missing vectors 0, vector-presence errors 0.
- Today's verdict: no model/provider attempt happened because the schedule skipped on the power
  gate.

### Transcript And RAG

- Transcript indexes: `memory-harden status --json` reported 3 indexes, 47 files, all processed.
- Latest successful transcript scan: 26 files seen, 3 ignored by config, 0 pending, 23 unchanged,
  0 skipped by cap, 0 summary failures, 0 requeued missing vectors, 0 vector-presence errors.
- RAG health: `http://localhost:8110/health` returned `{"status":"UP"}`.
- RAG metrics: unauthenticated `/metrics` returned HTTP 401, so no quantitative corpus/vector count
  was accepted as evidence in this public report.
- Browser transcript/recall answer proof was not run during this overnight audit; that remains a
  QA proof gap, not a product failure of the power-skipped overnight routine.

### Scheduler, Workbench, GlassHive

- Scheduler health: `/health` returned `ok` with public-safe runtime identity hashes.
- `bin/viventium status`: Scheduler running, 8 active / 20 total, last status success, delivery
  sent, next built-in Workbench run `2026-06-06T10:00:00Z`; Prompt Workbench, GlassHive, RAG,
  transcript ingest, and status-bar helper were running/configured.
- Active built-in task: `glasshive_host` / `workbench`, daily `03:00` America/Los_Angeles, next
  `2026-06-06T10:00:00Z`, last status success/sent.
- Latest built-in run: due `2026-06-05T10:00:00Z`, started `2026-06-05T10:00:09Z`, completed
  `2026-06-05T13:07:10Z`, private detail pointer present, error class empty.
- Recent built-in durations: Jun 2 190s, Jun 3 236s, Jun 4 202s, Jun 5 11,220s. Jun 5 is a
  performance warning, not a completion failure.
- GlassHive metrics: queued runs 0, active runs 0, callback pending 0, callback delivering 0,
  callback dead-lettered 2 historical rows, active max attempts 0.
- Callback DB: latest Jun 5 `run.completed` callback delivered in one attempt.
- Playwright UI: opened Workbench, selected the built-in schedule, confirmed enabled visible row,
  daily 03:00 America/Los_Angeles Workbench/GlassHive route, recent Jun 5 completed run, and
  Jun 5 proposal artifact listing. Browser was closed and temporary `.playwright-cli` artifacts were
  deleted.

### User-Level Provider Rows

- Four active user-level `viventium_agent` rows still carry provider-reconnect failure evidence
  from the prior day and next due `2026-06-05T15:00:00Z`.
- At this audit time they were **not due yet**, so they are account-action follow-up and not a June
  5 built-in nightly failure.

## Commands Run

Read-only/status commands:

- `date`, `TZ=UTC date`, `/etc/localtime` inspection
- `bin/viventium memory-harden status --json`
- `launchctl print gui/<uid>/ai.viventium.memory-harden`
- memory-hardener plist inspection
- selected generated-runtime/config key inspection with redaction
- `pmset -g batt`
- `pmset -g therm`
- hardener stdout/stderr tail/stat/grep with redaction
- memory-hardening run-directory listing
- `curl -sS http://localhost:7110/health`
- `curl -sS http://127.0.0.1:8780/v1/metrics/summary`
- `curl -sS http://localhost:8110/health`
- `curl -i -sS http://localhost:8110/metrics`
- SQLite read-only aggregate queries for scheduler and GlassHive DBs
- `bin/viventium status`
- `bin/viventium continuity-audit`
- `bin/viventium memory-dedupe --dry-run --json`
- Playwright CLI Workbench open/snapshot/click/snapshot/close, followed by `.playwright-cli`
  artifact deletion

Automated checks:

- `node qa/meeting-transcript-memory/evals/run-evals.cjs`: **12 passed, 0 failed**
- Initial `python3 -m pytest ...`: **not accepted**; global Python lacked `pytest`.
- First `uv run ... pytest ...`: **not accepted**; collection needed `croniter`.
- Final `uv run --with pytest --with pyyaml --with requests --with httpx --with fastapi --with fastmcp --with pydantic --with croniter python -m pytest tests/release/test_continuity_audit.py tests/release/test_memory_hardening_contract.py tests/release/test_rag_api_override_contract.py tests/release/test_scheduled_glasshive_prompts.py tests/release/test_prompt_workbench.py -q`: **152 passed, 2 warnings**
- `git diff --check`: **failed** on pre-existing trailing whitespace in
  `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`; not caused or
  modified by this audit.

## Findings

1. **Medium: memory hardening was skipped by the power gate, not failed.**
   The hardener due window had passed, but the wrapper recorded `on_battery_power`. This is the
   intended safety behavior for expensive model-backed work, so the correct status is **SKIPPED**.

2. **Medium: hardener schedule/cadence drift remains unresolved.**
   System/generated timezone is America/Toronto and the loaded LaunchAgent says 03:00 local, but
   recent success/skip evidence lands at `10:00Z` / 06:00 Toronto. This did not cause a false fail
   today because the observed effective due window had also passed and produced a power skip, but it
   remains a timing observability defect.

3. **Medium: Workbench completed but took 3h07m.**
   The full Workbench chain completed and the UI shows the Jun 5 run, but duration regressed from
   the recent 3-4 minute baseline to 11,220 seconds. Under the core outcome metric, this is a
   significant product performance regression even though the terminal status is completed.

4. **Medium: transcript/RAG product work skipped cleanly, but user-facing recall proof remains open.**
   The product-side transcript/RAG lifecycle did not fail; it was skipped because memory hardening
   power-gated. Index state, RAG health, and latest vector telemetry are healthy, but the browser
   recall/source-card path and authenticated vector-document proof were not rerun. Do not promote
   RAG to full pass from health checks alone.

5. **Low: user-level provider reconnect rows are not due yet today.**
   Four rows remain account-action follow-up, with next due after this audit. They should not be
   classified as this morning's built-in nightly failure.

6. **Low: dirty worktree and diff-check failure are unrelated audit hygiene risks.**
   The worktree was already broadly dirty; this audit does not revert or classify those changes as
   nightly-routine failures. The `git diff --check` failure is the same pre-existing trailing
   whitespace style issue.

## Claude Review

ClaudeViv was unavailable, so local Claude CLI was used as the review-only second opinion with tools
disabled and sanitized evidence only. It made no changes.

Confirmed:

- Overall **PARTIAL** is justified.
- Memory hardening is **SKIPPED**, not FAIL, because the due window passed and the wrapper recorded
  `on_battery_power`.
- Transcript/RAG should be split into clean product skip plus **QA proof gap**, not treated as a
  RAG runtime failure.
- Scheduler/GlassHive callback health is **PASS**.
- User-level provider reconnect rows were **NOT DUE** at audit time.
- Hardener 03:00 America/Toronto vs observed 10:00Z cadence is real product/config drift.

Adjustments incorporated:

- Workbench Jun 5 duration is now called a **significant performance regression** rather than a soft
  warning.
- RAG classification now separates product-side skip from user-path proof gap.
- Next actions prioritize Workbench stage-level timing and hardener cadence drift.

Unresolved risks from review:

- Workbench slow-run owner is not yet localized to model calls, retrieval, GlassHive worker time, or
  callback/update handling.
- Hardener timing drift is not yet localized to generated config, LaunchAgent reload/state, wrapper
  environment, or launchd timezone behavior.
- Authenticated RAG vector-document and browser source-card proof remain unrun.

## Next Actions

1. Capture stage-level timing for the Workbench nightly chain before the next run so a repeated
   50x-duration regression has an owner.
2. Investigate the memory-hardener timing drift read-only first: generated runtime schedule,
   LaunchAgent reconciliation, loaded launchd calendar interval, wrapper environment, and why
   observed runs/skips happen at `10:00Z` despite America/Toronto 03:00 config.
3. Run a separate authenticated RAG/browser recall QA pass with synthetic or sanitized transcript
   evidence before promoting transcript/RAG from partial to pass.
4. Keep the machine on AC before tomorrow's due window if a model-backed hardener apply is expected,
   and verify the next StartCalendarInterval fire is computed against the intended local time.
5. Add lightweight non-model schedule observability so future audits can distinguish loaded,
   fired-and-power-skipped, fired-and-idle-skipped, successful-empty, successful-apply, and missing
   launch without parsing private stderr.
6. Triage the four provider-reconnect rows through the connected-account owner surface after their
   `2026-06-05T15:00:00Z` due window.
