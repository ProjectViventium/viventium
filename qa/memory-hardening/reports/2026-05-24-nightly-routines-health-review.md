# 2026-05-24 Nightly Routines Health Review

Status: **FAIL / PARTIAL** for the overnight-routine contract.

Run time: 2026-05-24 04:03-04:22 local time, after the documented 03:00 local
memory-hardening and Workbench deep-thought schedules should have completed.

This report is public-safe. Raw App Support logs, schedule prompts, memory values, transcript
content, account emails, local absolute paths, DB ids, and helper tokens were not copied here.
Future scheduler-ownership audits that inspect process environments must redact env values before
sharing evidence, because that inspection path can expose secret-bearing runtime variables.

## Expected Overnight Routines

- Saved-memory hardening: enabled generated runtime config, daily schedule `0 3 * * *`, apply mode,
  full 7-day lookback, launch-ready Anthropic primary model, and transcript ingest enabled.
- Meeting transcript lane: source folder configured, ignore glob for sidecar bookkeeping, default
  `detailed_summary_only` RAG mode, processed-content index freshness, vector presence checks, and
  summary/inventory artifact lifecycle.
- Prompt Workbench scheduled prompt: enabled "Subconscious Deep Thought" Workbench-private schedule
  due daily at 03:00 America/Los_Angeles through Scheduling Cortex and GlassHive host execution.
- User-level scheduled routines: active Scheduling Cortex rows should advance due schedules and
  write delivery ledger state, with failures classified instead of silently stalling.
- Prompt Workbench evals: most recent eval artifacts should remain inspectable; no-live previews
  are not model-performance claims.

## Actual Results

- Saved-memory hardening did **not** run on 2026-05-24 by 04:03 local time.
  The latest persisted hardening run was `20260523T100024Z`, started at
  2026-05-23T10:00:24Z and finished successfully at 2026-05-23T10:20:30Z.
- No `ai.viventium.memory-harden` LaunchAgent plist or loaded launchctl job was present even though
  generated runtime env had `VIVENTIUM_MEMORY_HARDENING_ENABLED=true` and schedule `0 3 * * *`.
- The latest successful memory-hardening run applied `context` and `moments`, used Anthropic
  `claude-opus-4-7` at `xhigh`, fed all 556 lookback messages from 53 conversations, omitted
  0 messages for input-cap reasons, and recorded memory instructions as present.
- Transcript ingest state was caught up by deterministic index counts, but vector validation was
  degraded: latest run saw 26 source files, ignored 3 configured sidecars, had 23 unchanged files,
  0 pending/deferred/skipped/summary-failed files, and recorded 2 `vector_presence_auth_error`
  checks. No destructive transcript repair was observed.
- Transcript processed indexes showed 47 processed files across three scoped index files; the
  primary scoped index had 23 processed files, updated at the latest hardening finish time.
- Mongo read-only counts showed 35 `meeting_transcript` file rows and a latest meeting-transcript
  update at 2026-05-23T10:20:30Z. Conversation recall had one corpus file updated at
  2026-05-24T07:18:27Z.
- RAG `/health` returned `UP`; unauthenticated `/status` returned 401 as expected; API schema exposed
  `/documents/exists`, `/query`, and `/query_multiple`.
- Local-prod Scheduling Cortex state is stale. The local-prod scheduler log stopped on
  2026-05-23, active local-prod tasks still had overdue `next_run_at` values from
  2026-05-23, and the Workbench deep-thought row still showed `next_run_at=2026-05-24T10:00:00Z`
  after that due time had passed.
- The process currently answering `localhost:7110` was a separate dev-env scheduler, using that
  dev-env's scheduling DB and log files. This makes scheduler health look green while the
  local-prod scheduling DB is not being advanced.
- The dev-env scheduler DB was also stale enough that restoring port ownership alone should not be
  credited as recovery; GlassHive executor reachability needs its own follow-up check.
- The Workbench scheduled prompt due on 2026-05-23T10:00:00Z failed with `URLError` /
  connection refused to GlassHive. No 2026-05-24 scheduled-prompt run row existed by 04:03 local.
- Prompt Workbench itself was running standalone and loaded in Playwright. The browser-visible
  Prompt Flow showed scheduled prompt objects, including the Workbench deep-thought schedule still
  marked enabled and due at "next May 24, 3:00 AM" after the due window.

## Commands And Checks Run

- `bin/viventium status`:
  local-prod reported core services still starting; Conversation Recall was running; Telegram was
  stopped; Docker-backed search/MCP services were starting.
- `bin/viventium dev-env run <dev-env-name> status`:
  dev env reported ready on its separate app-facing ports.
- `bin/viventium memory-harden status`:
  116 total runs, 106 summarized, 10 empty, 4 failed; latest run was
  `20260523T100024Z`, apply, success.
- `bin/viventium transcripts source status --json`:
  transcript source was configured. The raw source path is private and omitted.
- LaunchAgent inspection:
  no memory-hardening LaunchAgent plist or loaded launchctl job was found.
- SQLite read-only scheduler inspection:
  local-prod `scheduled_tasks` and `scheduled_prompt_runs` showed overdue/stale rows; dev-env DB
  was separate and actively attached to the live scheduler process on port 7110.
- Mongo read-only inspection:
  collection counts, memory key counts by hashed user, meeting transcript file counts by hashed
  user, and listen-only message count were checked without dumping raw values or ids.
- RAG health/API-shape checks:
  `/health` passed; `/status` required auth; relevant document/query endpoints were present.
- Prompt Workbench private-state summaries:
  latest no-live preview eval artifact was 2026-05-22T23:22:35Z with 3 selected cases; the last
  exact-model eval artifacts found were 2026-05-21 local live runs with public-safe reports;
  draft states were only `applied` or `discarded`.
- Playwright CLI:
  loaded the running Prompt Workbench and captured a DOM snapshot confirming the visible scheduled
  prompt group and stale due schedule state.
- Automated regression/eval checks:
  - `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi python -m pytest tests/release/test_memory_hardening_contract.py tests/release/test_config_compiler.py tests/release/test_scheduling_mcp_supervision.py tests/release/test_prompt_workbench.py -q`
    passed: 191 passed, 16 skipped.
  - `node qa/meeting-transcript-memory/evals/run-evals.cjs` passed: 12 passed, 0 failed.
  - `bin/viventium memory-dedupe --dry-run --json` passed read-only: 0 duplicate memory groups,
    0 duplicate key groups, 0 deletes, no index creation.

## Status By Goal

| Goal | Status | Evidence |
| --- | --- | --- |
| Memory hardening scheduled apply | **FAIL** | Enabled runtime config but no LaunchAgent and no 2026-05-24 run after due time. |
| Transcript ingest/catch-up | **PARTIAL** | Processed index counts are caught up; latest run had 0 pending/deferred files but 2 vector-presence auth errors. |
| Transcript summary/RAG artifacts | **PARTIAL** | Mongo rows and RAG health exist; vector-presence returned `vector_presence_auth_error` for 2 checks, and per-file reasons are not enumerated in the run summary. |
| Prompt Workbench scheduled deep-thought routine | **FAIL** | Prior run failed with connection refused; current due row remained overdue with no 2026-05-24 run. |
| User-level scheduler routines | **FAIL** | Local-prod tasks had stale overdue next-run timestamps; dev-env process was answering the shared scheduler port. |
| Prompt Workbench eval artifacts | **PASS / PARTIAL** | No-live preview artifacts inspectable; no fresh exact-model live eval since 2026-05-21. |
| Scheduler/LaunchAgent state | **FAIL** | Memory LaunchAgent missing; local-prod scheduler stopped; dev-env scheduler creates false-positive health. |
| Model/provider/fallback telemetry | **PASS with warning** | Latest hardener selected configured Anthropic candidate and recorded probe success; vector auth errors remain. |
| Status-bar/manual-ingest state | **NOT RUN** | Helper was running, but manual ingest was not triggered because this audit was read-only. |
| Public/private safety | **PASS** | Report uses counts, timestamps, hashes, placeholders, and sanitized status only. |

## Findings

1. **P1: Nightly memory hardening is not scheduled.**
   The generated runtime says memory hardening is enabled, but the macOS LaunchAgent is absent and
   the expected 2026-05-24 03:00 local run did not happen.

2. **P1: Scheduler health is cross-wired to a dev env.**
   Port 7110 is occupied by a separate dev-env scheduler using its own DB, while the
   local-prod scheduling DB has stale due rows. Health checks against `localhost:7110` can therefore
   pass for the wrong runtime.
   The attached dev-env DB is also not current enough to prove delivery health, so the repair must
   verify both local-prod ownership and GlassHive executor reachability.

3. **P1: Workbench scheduled deep-thought routine is not delivering.**
   The latest scheduled-prompt run failed with connection refused, and the next due run remained
   overdue with no run row after the 03:00 local due time.

4. **P2: Transcript vector presence validation is degraded.**
   The latest hardening run correctly avoided destructive assumptions, but 2 vector-presence checks
   failed with auth-class errors. This must be repaired before claiming transcript RAG is fully
   healthy.

## ClaudeViv Review

ClaudeViv review-only JSON completed after the evidence pass. It confirmed the four provisional
findings and the FAIL/PARTIAL status mapping: missing memory-hardening LaunchAgent/no current run,
dev-env scheduler ownership of port 7110, Workbench scheduled-prompt non-delivery, and transcript
`vector_presence_auth_error` degradation.

Confirmed additions incorporated here:

- Restoring scheduler port ownership is necessary but may not be sufficient because the dev-env
  scheduler DB also looked stale; executor reachability must be verified before declaring recovery.
- Process-environment inspection is useful for proving scheduler ownership but can expose secrets,
  so future audit evidence must redact env values before entering reports, prompts, or handoffs.
- A transient Claude CLI timeout note observed during investigation was not cited in this public
  report because the persisted latest hardening run summary recorded `status=success`.

## Not Run

- No hardener dry-run/apply, transcript ingest, LaunchAgent install, scheduler restart, or dev-env
  stop was performed because this was a read-only audit.
- No authenticated LibreChat browser memory/recall prompt was sent.
- No exact-model live Prompt Workbench eval was started.
- No status-bar manual transcript ingest action was triggered.

## Recommended Next Actions

1. Restore the local-prod scheduler boundary:
   stop or move the separate dev-env scheduler off the local-prod scheduler port, then
   restart local-prod and verify the scheduler process is attached to the local-prod scheduling DB.
   Then verify GlassHive executor reachability with sanitized synthetic input before crediting the
   scheduler as recovered.
2. Reconcile the memory-hardening LaunchAgent:
   run the documented schedule install path from generated runtime config, verify the plist,
   launchctl loaded state, and next 03:00 local dry-run/apply guard behavior.
3. Repair Workbench scheduled prompt delivery:
   after scheduler ownership is corrected, verify GlassHive host availability and run one
   operator-approved synthetic Workbench scheduled-prompt manual run or wait for the next scheduled
   run; confirm ledger status, private detail pointer, and no raw prompt leakage.
4. Resolve transcript vector auth errors:
   inspect RAG/vector auth configuration and rerun a read-only/vector-presence check or scoped
   transcript ingest dry-run; do not claim full transcript RAG health until vector-presence errors
   are 0.
5. Rerun this report's checks after repair and update the touched case rows again.
