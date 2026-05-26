# 2026-05-26 Nightly Routines Health Review

Status: **FAIL** for the overnight-routine contract.

Run time: 2026-05-26 04:01-04:22 local time, after the documented 03:00 local
memory-hardening and Workbench deep-thought schedules should have completed.

This report is public-safe. Raw App Support logs, schedule prompts, memory values, transcript
content, account emails, local absolute paths, DB ids, launch tokens, screenshots, and private
conversation text were not copied here.

## Summary

- Result: **FAIL** overall.
- Primary blockers: Scheduling Cortex was down, Prompt Workbench was down, the 03:00 Workbench
  nightly row remained overdue, and transcript vector work deferred because the RAG/vector runtime
  was unreachable.
- Partial success: the memory-hardening LaunchAgent fired at 03:00 local, exited 0, completed the
  bounded chat-memory lookback, and made no unsafe memory writes.
- Supporting checks: focused release regressions passed, transcript evals passed, memory-dedupe
  dry-run was clean, and ClaudeViv review confirmed the strengthened severity.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MEMHARD-001` | PARTIAL | Latest 03:00 hardener run exited 0, but transcript vectors deferred as RAG/vector unavailable. | Memory apply success is not equivalent to current transcript/RAG state. |
| `MEMHARD-002` | PASS | Report and case updates use sanitized counts, timestamps, statuses, and feature identifiers. | Raw runtime, browser, DB, and transcript evidence omitted. |
| `MTM-006` | BLOCKED | RAG/vector health endpoints unavailable. | Browser transcript-recall signoff was not attempted. |
| `MTM-013` | PARTIAL | 36 vector-presence checks failed; no destructive repair occurred. | Follow-up requires healthy RAG and zero vector-presence errors. |
| `SCHED-002` | FAIL | Scheduler listener unavailable; 03:00 Workbench row overdue; no current nightly run row. | User-visible scheduled routine did not execute. |
| `PW-029` | FAIL | Playwright browser showed Workbench connection refused. | Source tests passed, but live Workbench acceptance is blocked. |
| `MEMCONT-001` | BLOCKED/PARTIAL | Continuity capture skipped Mongo because generated `MONGO_URI` was blank. | Direct sanitized Mongo queries filled this run's evidence gap only. |

## Traceability

- Feature: Viventium overnight routines QA.
- Requirement: `docs/requirements_and_learnings/20_Memory_System.md`,
  `docs/requirements_and_learnings/11_Scheduling_Cortex.md`,
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`, and
  `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`.
- Use case: verify scheduled memory hardening, transcript ingest/RAG lifecycle, Workbench scheduled
  deep-thought routine, scheduler state, prompt eval surface, and helper/manual-ingest state after
  the nightly window.
- QA case: `MEMHARD-001`, `MEMHARD-002`, `MTM-006`, `MTM-013`, `SCHED-002`, `PW-029`,
  `MEMCONT-001`, and `MEMCONT-002`.
- Expected result: scheduled jobs advance, vector/RAG lifecycle is current or honestly deferred,
  Workbench/Scheduler user surfaces are reachable, and evidence is public-safe.
- Actual evidence: memory LaunchAgent fired, but Scheduler/Workbench/RAG were unreachable;
  scheduler DB showed the Workbench row overdue; hardener telemetry recorded vector deferral.
- Remaining gap or fix: restart/repair the local runtime, then re-probe Scheduler, Workbench,
  RAG/vector, and the scheduled run ledger before accepting the next nightly result.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Overnight routines across memory, transcript RAG, Scheduling Cortex, Prompt Workbench, and memory continuity. |
| Code owning path | Which code path owns the behavior? | Memory hardener wrapper, Scheduling Cortex SQLite loop, Prompt Workbench service, RAG/vector sidecar, generated runtime env. |
| Docs and nested docs | Which docs define expected behavior? | Required docs listed in Traceability plus owning QA cases. |
| Logs | Which sanitized logs confirm or contradict the result? | Memory hardening logs showed vector-presence errors; helper logs showed no compensating manual ingest. |
| DB/state/persistence | Which sanitized state confirms it? | Memory run summary, scheduler DB counts/timestamps, Mongo counts, continuity capture warning. |
| Generated/shipped artifact | Which generated config was inspected? | Generated runtime env showed memory hardening enabled, transcript RAG mode configured, scheduler port set, Workbench not stack-managed. |
| Real user path | Which user path was exercised? | Playwright browser open and snapshot against Prompt Workbench showed connection refused. |
| Visible UX comparison | Did visible state match supporting evidence? | Yes: browser-visible Workbench outage matched missing service and overdue scheduler DB state. |
| Not run / blocked | Which required surface was not run? | Browser transcript recall, exact-model Workbench eval, scheduler restart, GlassHive run, and manual ingest were not run in this read-only audit. |

## User-Grade Evidence

- Surface exercised: Playwright browser, CLI status, scheduler state, memory hardener status, and
  read-only DB/log inspection.
- Real user path: opened Prompt Workbench in a real browser after the nightly window; the browser
  showed `ERR_CONNECTION_REFUSED`.
- Visible outcome: the Workbench UI was unavailable, so the scheduled prompt/eval surface could not
  be inspected by a user.
- Expanded/detail state: Playwright snapshot captured the browser error details; scheduler DB state
  showed the 03:00 Workbench row overdue with no current run row.
- Persistence/reload result: no schedule or memory state was changed; persisted scheduler state
  remained overdue, and transcript vector rows did not update during the current hardener run.
- Backend/log/DB confirmation: hardener summary recorded `vector_runtime_unreachable`; endpoint
  probes showed RAG/Scheduler/Workbench unavailable; continuity capture warned that Mongo
  introspection was skipped.
- Final model/runtime wording check: no model answer was generated; the runtime state and browser
  error both indicated blocked/unavailable service rather than successful completion.
- Substitution check: source tests, logs, and DB rows supported the result, but did not replace the
  Playwright browser check for Workbench or the blocked status for transcript browser recall.

## Expected Overnight Routines

- Saved-memory hardening: enabled generated runtime config, daily `0 3 * * *` local schedule,
  apply mode, full 7-day lookback, Anthropic primary model with fallbacks, and transcript ingest
  enabled.
- Meeting transcript lane: configured transcript source, sidecar ignore glob, summary-only RAG
  mode, vector presence checks, and current summary/inventory artifact lifecycle.
- Prompt Workbench scheduled prompt: enabled **Subconscious Deep Thought** Workbench-private
  schedule due daily at 03:00 local through Scheduling Cortex and GlassHive host execution.
- User-level scheduled routines: active Scheduling Cortex rows should advance due schedules and
  write delivery ledger state, with failures classified instead of silently stalling.
- Prompt Workbench evals: recent eval artifacts should remain inspectable; no-live previews are not
  model-performance claims.
- Status-bar/helper manual ingest: helper state should not imply a completed manual ingest when no
  user-triggered ingest ran.

## Actual Results

- Saved-memory hardening **did run** at the expected 03:00 local schedule. The latest run started at
  2026-05-26T10:00:04Z, finished at 2026-05-26T10:00:31Z, exited successfully, used
  `anthropic / claude-opus-4-7 / xhigh`, and completed the full 7-day lookback.
- The hardener made no durable memory changes in this run: 7 messages from 1 conversation were
  considered, no input-cap clipping occurred, no model-attempt failures were recorded, and
  `changed_keys=[]`.
- Transcript/RAG work **did not complete**. RAG/vector endpoints were unreachable; the hardener
  recorded `vector_presence_error_count=36`, `vector_presence_check_failed`,
  `transcript_vectors.deferred=true`, and `reason=vector_runtime_unreachable`.
- The latest hardener uploaded 0 transcript vectors and deleted 0 stale vectors. Aggregate
  transcript state still reports 3 files deferred by cap from the backlog.
- Scheduling Cortex was not listening on the configured local scheduler port during the audit.
- Prompt Workbench was not listening. A real Playwright browser open of the Workbench URL produced
  `ERR_CONNECTION_REFUSED`.
- The active Workbench nightly task remained overdue for the 2026-05-26 03:00 local run. The
  scheduler DB had no 2026-05-26 scheduled-prompt run row for the nightly Workbench routine.
- User-level agent schedules were not overdue at the audit time, but 9 active rows still carried a
  prior `missed` status/outcome and need a separate executor health follow-up.
- Prompt Workbench eval/source contracts remain intact at the source-test level, but live Workbench
  eval inspection is **blocked** while the Workbench service is down.
- The status-bar helper had quit after a prior stack stop, and manual transcript ingest logs showed
  no user-triggered ingest since 2026-05-15. No manual ingest was triggered during this read-only
  audit.

## Evidence Checked

- LaunchAgent/plist state: memory hardening installed, loaded, 03:00 local calendar, direct
  `env -i` wrapper invocation, App Support working directory, and last exit code 0.
- Generated runtime config: memory hardening enabled, transcript source configured,
  `detailed_summary_only` transcript RAG mode, max 20 transcript files per run, Ollama embeddings
  configured for RAG, scheduler port configured, and stack-managed Prompt Workbench disabled.
- Memory hardening state: latest run `20260526T100004Z`, apply mode, successful model probe,
  complete lookback, no memory writes, and redacted vector-presence error telemetry.
- Runtime probes: scheduler, Workbench, and RAG/vector endpoints were unavailable; native Mongo was
  the only relevant local listener found.
- Scheduler SQLite summaries: 14 scheduled tasks, 11 active, 1 active overdue Workbench/GlassHive
  row for the 03:00 local run, and no 2026-05-26 nightly Workbench run row.
- Mongo read-only summaries: saved-memory, message, conversation, meeting-transcript vector-backed
  file rows, and conversation-recall vector-backed file rows were present; vector-backed file rows
  were stale relative to the current hardener run because RAG was unavailable.
- Continuity audit capture: returned `warning`; schedule metadata was visible, but Mongo
  introspection was skipped because generated runtime `MONGO_URI` is blank/quoted.
- Playwright CLI: opened the Workbench URL and captured the browser error snapshot showing
  connection refused.
- Git drift: parent repo already contained unrelated GlassHive docs/QA edits before this report;
  nested LibreChat was clean during this audit.

## Automated Evidence

- `bin/viventium status`: reported the install configured but not user-facing live; core browser/API
  and optional sidecar surfaces were not running.
- `bin/viventium memory-harden status`: latest scheduled run succeeded; aggregate transcript state
  still had processed and deferred-cap entries.
- Local endpoint probes for scheduler, Workbench, and RAG/vector health: all unavailable.
- Sanitized SQLite queries over Scheduling Cortex state: confirmed the overdue Workbench nightly row
  and latest run/update timestamps.
- Sanitized Mongo queries over the local native DB: confirmed continuity surfaces exist while
  vector-backed file rows did not update during the current hardener run.
- `python3 scripts/viventium/continuity_audit.py capture ...`: returned `warning` because Mongo
  introspection was skipped.
- `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi --with fastmcp
  python -m pytest tests/release/test_memory_hardening_contract.py
  tests/release/test_config_compiler.py tests/release/test_scheduling_mcp_supervision.py
  tests/release/test_prompt_workbench.py tests/release/test_scheduled_glasshive_prompts.py -q`:
  **217 passed**, 1 warning.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`: **12 passed**, 0 failed.
- `bin/viventium memory-dedupe --dry-run --json`: 0 duplicate memory groups, 0 duplicate key groups,
  0 deletes, no index creation.
- Playwright CLI Workbench open + snapshot: blocked by `ERR_CONNECTION_REFUSED`, proving the live
  Workbench user surface was down.

## Status By Goal

| Goal | Status | Evidence |
| --- | --- | --- |
| Memory hardening scheduled apply | **PARTIAL** | LaunchAgent fired and exited 0 with full lookback, but transcript vector work was deferred and no current vector lifecycle was proven. |
| Transcript ingest/catch-up | **FAIL / PARTIAL** | 36 vector-presence checks failed, RAG was unreachable, 0 vectors uploaded/deleted, and 3 deferred-cap files remain in aggregate state. |
| Transcript summary/RAG artifacts | **FAIL** | Existing Mongo file rows were present but stale relative to the current run; live RAG/vector health was unavailable. |
| Prompt Workbench scheduled deep-thought routine | **FAIL** | 03:00 local Workbench task was overdue, no 2026-05-26 run row existed, and Workbench was unreachable. |
| User-level scheduler routines | **PARTIAL / RISK** | No active user-level row was overdue at audit time, but 9 active rows carried prior `missed` status/outcome. |
| Prompt Workbench eval artifacts | **BLOCKED / PARTIAL** | Source tests passed, but live Workbench eval inspection was blocked by service unavailability. |
| Scheduler/LaunchAgent state | **FAIL** | Memory LaunchAgent healthy; Scheduling Cortex listener down and the 03:00 Workbench row did not advance. |
| Model/provider/fallback telemetry | **PASS** | Anthropic primary probe succeeded; no fallback failure or model-attempt failure was recorded. |
| Status-bar/manual-ingest state | **PARTIAL** | Helper was not running and no manual transcript ingest occurred; no compensating ingest path ran. |
| Public/private safety | **PASS** | Report uses sanitized counts, timestamps, statuses, and feature identifiers only. |

## Findings

1. **P1: Scheduling Cortex is down and the 03:00 Workbench nightly routine missed.**
   The scheduler listener was unavailable, the active built-in Workbench schedule was overdue, and
   there was no 2026-05-26 run row for the expected nightly routine.

2. **P1: Prompt Workbench is down, blocking live schedule/eval inspection.**
   Playwright reached a browser error page with connection refused, so source tests cannot be
   treated as user-grade Workbench acceptance.

3. **P2: Transcript vector lifecycle is degraded.**
   The hardener run succeeded only for the chat-memory portion. Transcript vector presence checks
   failed, vector writes were deferred as `vector_runtime_unreachable`, and aggregate deferred-cap
   backlog remains.

4. **P2: Continuity audit cannot introspect Mongo from the generated runtime env.**
   The capture warned that Mongo was skipped because `MONGO_URI` is blank/quoted. Direct sanitized
   Mongo queries compensated for this audit, but the reusable audit remains incomplete.

5. **P2: Multiple active user-level schedules carry prior missed status.**
   They were not overdue at 04:01 local, but the carried-forward `missed` state suggests executor
   degradation that should not be hidden under the Workbench nightly failure.

6. **P3: Helper/manual-ingest state offers no compensating path.**
   The helper had quit after a prior stack stop, and manual transcript ingest had not run recently.

## ClaudeViv Review

ClaudeViv review-only JSON completed after the evidence pass. It returned `changes_requested` and
confirmed the core findings: memory hardening fired but was only partial, transcript/RAG work was
degraded, Scheduling Cortex and Workbench were down, the 03:00 Workbench routine missed, and the
public report must stay sanitized.

Adjustments incorporated from ClaudeViv:

- Overall nightly status is **FAIL**, not partial pass.
- Scheduling Cortex listener down plus overdue Workbench row is **P1**.
- Prompt Workbench unreachable plus no 2026-05-26 nightly run row is **P1**.
- Transcript/RAG degradation is **P2** and should not be normalized as a clean memory-hardening pass.
- The blank generated `MONGO_URI` continuity-audit gap is **P2**.
- QA case rows should be updated for memory hardening, meeting transcript memory, scheduling,
  prompt workbench, and memory continuity.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private prompts, private chats, raw transcripts, customer data, personal emails, or
  screenshots with private content.
- [x] No account identifiers, conversation IDs, message IDs, session/call IDs, Telegram chat IDs,
  Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute home paths, hostnames, machine names, stack traces with private paths,
  database exports, App Support dumps, or raw runtime dumps.
- [x] Private evidence is summarized only with sanitized counts, timestamps, statuses, and feature
  identifiers.

## Not Run

- No memory hardening apply/dry-run, transcript ingest, scheduler restart, stack restart,
  Workbench manual run, GlassHive worker run, or exact-model live eval was triggered.
- No authenticated LibreChat browser memory/recall prompt was sent.
- No owner memory, conversation, transcript, or schedule state was intentionally mutated as part of
  this audit.

## Recommended Next Actions

1. With operator approval, restart the active local runtime through the supported product path, then
   re-probe scheduler, Workbench, RAG/vector, LibreChat API, and browser surfaces.
2. After recovery, verify the Workbench nightly task either catches up according to the documented
   policy or records an honest missed/degraded ledger; then run a synthetic, public-safe scheduled
   prompt if manual proof is approved.
3. Re-run the memory hardener status check after RAG is healthy. Acceptance requires
   `vector_presence_error_count=0`, no `vector_runtime_unreachable`, completed vector uploads or
   verified no-op vector state, and no deferred-cap backlog.
4. Fix or extend `continuity_audit.py` so local Mongo continuity can be inspected when generated
   `MONGO_URI` is intentionally blank.
5. Investigate why active user-level scheduler rows accumulated `missed` outcomes and whether the
   GlassHive executor/backpressure findings from 2026-05-25 are still contributing.
6. Keep this report and linked case rows public-safe; raw logs, private detail files, transcripts,
   prompts, and screenshots remain outside the public repo.
