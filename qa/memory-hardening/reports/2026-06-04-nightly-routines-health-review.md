<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-06-04 Nightly Routines Health Review

## Summary

Overall status: **PARTIAL**, with a **FAIL** for the June 4 memory-hardening scheduled execution.

This was a read-only overnight-routine audit at `2026-06-04T08:03:25Z`
(`2026-06-04 04:03` America/Toronto). No model-backed apply, transcript ingest/catch-up,
rebuild, repair, background-agent work, runtime stop, Docker stop, data reset, or owner memory/chat
mutation was started by this audit.

Public-safety rule for this report: raw operator account values, local App Support paths, transcript
filenames/text, private schedule prompts, prompt-workbench launch tokens, private detail paths,
callback payloads, browser snapshots, and screenshots are omitted. Evidence below uses only
sanitized counts, statuses, hashes, labels, and timestamps.

## Expected Vs Actual Routines

| Routine | Expected | Actual evidence | Status |
| --- | --- | --- | --- |
| Memory hardening | `0 3 * * *` local, configured for America/Toronto, via LaunchAgent wrapper | LaunchAgent label was loaded and configured for hour `3`, minute `0`; machine was AC/awake/thermally clean; no `20260604*` run directory, no June 4 hardener stdout/stderr update, and no launchd event from 02:30-04:05 local. Latest successful run remained `20260603T100007Z`. | **FAIL** |
| Transcript ingest/catch-up inside hardener | Scan configured transcript source and keep summary/RAG lifecycle current | Latest successful hardener run saw 26 transcript files, 3 ignored by config, 0 pending, 0 skipped by cap, 0 requeued missing vectors, and 0 vector-presence errors. Three private transcript indexes total 47/47 processed. No fresh June 4 hardener ran. | **PARTIAL** |
| Transcript summary/RAG artifacts | Keep detailed-summary-only RAG artifacts healthy and recallable | RAG `/health` returned `UP`; unauthenticated `/metrics` returned 401 as expected; no authenticated vector-document proof or browser recall/source-card answer was rerun. | **PARTIAL** |
| Workbench nightly reflection | Built-in `Subconscious Deep Thought` via Scheduler -> GlassHive -> callback -> Workbench | June 3 due run completed at `2026-06-03T10:04:07Z`. June 4 run was not due at audit time; next due was `2026-06-04T10:00:00Z`. Playwright confirmed the schedule enabled and recent completed runs visible. | **PASS for Jun 3; NOT DUE/PARTIAL for Jun 4** |
| Scheduler / GlassHive callback health | No fresh callback backlog or silently degraded delivery substrate | Scheduler health ok; built-in Workbench task last status success; GlassHive metrics had 0 queued/active runs, 0 pending/delivering callbacks, and 2 historical dead-letter rows only. Four active user-level provider-reconnect rows remain recurring account-action issues. | **PASS/PARTIAL** |
| Prompt Workbench evals | No scheduled exact-model benchmark expected overnight; manual fixture checks should pass when run | Latest private Workbench eval metadata was a May 30 synthetic no-live preview. This audit ran focused release tests and transcript eval fixtures successfully. | **N/A scheduled; PASS manual fixtures** |
| Continuity / dedupe | Continuity audit ok and no memory duplicate dry-run changes | Continuity audit status `ok`; memory-dedupe dry-run reported 0 duplicate groups/docs/deletes for memory entries and keys. | **PASS/PARTIAL** |
| Power / heat gate | Expensive model work must skip on battery or thermal constraint | AC attached, battery present, no thermal/performance warning, awake around local 03:00. No power-budget skip and no override flags used. | **PASS** |

## Evidence Checked

### Power And Launch State

- Battery/power: AC attached, battery at 80%.
- Thermal/performance: no warning recorded.
- Power log: awake/no-idle assertions around local 03:00; no sleep explanation for missed hardener.
- LaunchAgent: one Viventium memory-hardener label found and loaded in the GUI domain, with
  `StartCalendarInterval` hour `3`, minute `0`, direct wrapper invocation, App Support working
  directory, and last exit code `0`.
- Duplicate-label check: only the expected memory-hardener LaunchAgent file was found.

### Memory Hardening

- Generated runtime config: hardening enabled, schedule `0 3 * * *`, timezone `America/Toronto`,
  dry-run-first on, configured OpenAI/GPT-5.5 route, scoped to one redacted operator user.
- Run state: latest run `20260603T100007Z`, mode `apply`, provider OpenAI, model GPT-5.5, status
  success, finished `2026-06-03T10:03:34Z`, one selected/applied user.
- Latest redacted run telemetry: one model attempt, zero model failures, zero fallback, full
  lookback complete, 430 messages fed, transcript pending 0, requeued missing vectors 0,
  vector-presence errors 0.
- Apply result: three bounded memory keys changed, maintenance applied, transcript vector
  uploads/deletes/deferred all 0.
- Missing June 4 evidence: no `20260604*` run directory, no June 4 hardener stdout/stderr mtime, and
  no launchd event in the queried 02:30-04:05 local window.

### Transcript And RAG

- Transcript indexes: three private user/source indexes, 47 total files, all status `processed`.
  Counts by index were 23, 23, and 1. The main current-source index was updated by the June 3 run.
- RAG health: `/health` returned `UP`.
- RAG metrics: unauthenticated `/metrics` returned 401, so no quantitative corpus/vector count was
  accepted as evidence in this audit.
- No browser chat recall answer or persisted source-card proof was run.

### Scheduler, Workbench, GlassHive

- Scheduler status: running, but user-facing status still reports issues because four active
  user-level rows are recurring provider-reconnect failures. They were created before this audit
  period and last failed again at `2026-06-03T15:00:15Z`.
- Scheduler DB: 20 tasks total, 8 active, 31 scheduled prompt runs.
- Built-in Workbench task: active `glasshive_host` / `workbench`, next due
  `2026-06-04T10:00:00Z`, last run `2026-06-03T10:00:10Z`, last status success/sent.
- Latest built-in run: due `2026-06-03T10:00:00Z`, completed `2026-06-03T10:04:07Z`, hashes present,
  private detail pointer present.
- GlassHive metrics: queued runs 0, active runs 0, pending callbacks 0, delivering callbacks 0,
  historical dead-letter callbacks 2, active callback max attempts 0.
- Playwright UI: Prompt Workbench loaded, schedule row selected, detail panel showed enabled daily
  `03:00` America/Los_Angeles Workbench/GlassHive route, and recent runs completed on June 3,
  June 2, and June 1. Temporary Playwright snapshots were deleted and the browser was closed.

## Commands Run

Read-only/status commands:

- `bin/viventium status --json` (returned human-readable status; sanitized above)
- `bin/viventium memory-harden status --json`
- `launchctl print gui/<uid>/ai.viventium.memory-harden`
- `pmset -g batt`
- `pmset -g therm`
- `pmset -g log` filtered around the local 03:00 window
- `curl -sS http://localhost:7110/health`
- `curl -sS http://127.0.0.1:8780/v1/metrics/summary`
- `curl -sS http://localhost:8110/health`
- `curl -i -sS http://localhost:8110/metrics`
- SQLite read-only aggregate queries for scheduler and GlassHive DBs
- `bin/viventium continuity-audit`
- `bin/viventium memory-dedupe --dry-run --json`
- Playwright CLI Workbench open/snapshot/click/snapshot/close

Automated checks:

- `node qa/meeting-transcript-memory/evals/run-evals.cjs`: **12 passed, 0 failed**
- `PYTHONPATH=. uv run --with pytest --with PyYAML --with pydantic --with croniter --with fastapi pytest tests/release/test_memory_hardening_contract.py tests/release/test_continuity_audit.py tests/release/test_default_nightly_routines.py tests/release/test_scheduled_glasshive_prompts.py tests/release/test_prompt_workbench.py -q`: **133 passed, 22 skipped**
- `git diff --check`: **failed** on pre-existing trailing whitespace in
  `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`; not caused or
  modified by this audit.

Environment note: bare `python3 -m pytest` and earlier `uv run pytest` attempts failed because the
active local Python/ephemeral environment lacked pytest and then focused collection dependencies.
The final minimal `uv --with ...` invocation above passed.

## Findings

1. **High: June 4 memory-hardening scheduled execution failed.**
   The configured and loaded schedule should have produced a local 03:00 run, but there is no June 4
   run/log/launchd evidence despite AC, awake, and clean thermal preconditions.

2. **High: memory-hardening schedule drift is now the likely root-cause lane.**
   Recent successful hardener runs align with `10:00Z`, which is 06:00 America/Toronto, while
   generated runtime config says `0 3 * * *` in America/Toronto and the loaded LaunchAgent says
   hour `3`. This config-vs-observed cadence drift needs direct schedule-source investigation.

3. **Medium: transcript/RAG remains partial, not full pass.**
   Processed indexes and clean vector telemetry are strong support, but no fresh June 4 hardener ran
   and no authenticated vector-document or browser recall proof was rerun.

4. **Medium: scheduler user-level provider reconnect failures are recurring.**
   Four active user-level rows failed again after the prior audit window and keep the Scheduler
   status as “running with issues.” They are not the built-in nightly Workbench chain, but they need
   connected-account owner follow-up.

5. **Low: callback dead-letter rows are historical only.**
   Two dead-letter rows remain in the GlassHive callback outbox, but there is no active backlog and
   the newest built-in Workbench callback was delivered.

6. **Low: dirty worktree and diff-check failure are unrelated audit hygiene risks.**
   The worktree was already broadly dirty; this audit does not revert or classify those changes as
   nightly-routine failures.

## ClaudeViv Review

No separate `ClaudeViv` binary was available, so the local Claude CLI was used as the ClaudeViv
review path with tools disabled and sanitized evidence only. It returned structured JSON and made no
changes.

Confirmed by ClaudeViv:

- Overall `PARTIAL` is justified.
- Memory hardening is a clean **FAIL** for the June 4 local 03:00 scheduled run.
- June 3 `20260603T100007Z` is valid health evidence but stale for today's expected run.
- Workbench was **not due** for June 4 at the audit time and the June 3 Workbench run is well
  supported by DB, callback, GlassHive, and Playwright evidence.
- Transcript/RAG must remain **PARTIAL** because user-path recall/vector proof was not run.
- Power-gate classification is **PASS**.

ClaudeViv gaps and adjustments incorporated:

- Elevate the 10:00Z-vs-03:00 America/Toronto hardener cadence drift to a first-class high-severity
  finding.
- Treat the active user-level provider-reconnect rows as a recurring partial signal, not just
  decorative status text.
- Classify transcript ingest as **PARTIAL only**, not PASS/PARTIAL, for this audit.
- Treat Workbench evals as manual fixture PASS / scheduled benchmark N/A.
- Explicitly exclude missing local pytest deps, dirty worktree, and pre-existing whitespace from
  the nightly verdict.

## Next Actions

1. Investigate the hardener schedule drift without forcing model work: compare generated runtime
   schedule, LaunchAgent reconciliation, wrapper schedule export, launchd load timing, and why recent
   successful hardener runs land at `10:00Z` instead of `07:00Z` for America/Toronto.
2. Add or expose lightweight non-model schedule observability for the hardener so future audits can
   distinguish unloaded, loaded-after-due, launchd-skipped, wrapper-started, power-skipped, and
   successful-empty states without parsing private logs.
3. Run a follow-up after `2026-06-04T10:00:00Z` to confirm today's Workbench run completed, callback
   delivery stayed clean, and the visible Workbench recent-runs panel updated.
4. Run a separate authenticated RAG/browser recall QA pass with synthetic or sanitized transcript
   evidence before promoting transcript/RAG from partial to pass.
5. Triage the four active user-level provider-reconnect rows through the connected-account owner
   surface, then record whether they are expected account-action rows or stale scheduler failures.
6. Keep the historical GlassHive callback dead-letter count visible but do not treat it as a current
   regression unless a fresh delta appears.
