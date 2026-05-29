# 2026-05-27 Nightly Routines Health Review

Status: **FAIL** for the overnight-routine contract.

Run time: 2026-05-27 03:50-04:13 local time, after the documented 03:00 local
memory-hardening and Workbench deep-thought schedules should have completed.

This report is public-safe. Raw App Support logs, LaunchAgent payloads, schedule prompts, memory
values, transcript content, account emails, local absolute paths, DB ids, launch tokens, screenshots,
and private conversation text were not copied here.

## Summary

- Result: **FAIL** overall.
- Improved since 2026-05-26: the core runtime, Scheduler, and Prompt Workbench were reachable; the
  03:00 Workbench schedule advanced instead of staying overdue.
- Primary blockers: transcript vector/RAG remained unavailable because the configured local
  embeddings runtime was not listening, and the 03:00 Workbench/GlassHive routine failed terminally
  with a dispatch `HTTP 404` class.
- Partial success: the memory-hardening LaunchAgent fired at 03:00 local, exited 0, completed the
  full lookback, and applied validated changes to two generic saved-memory keys.
- Supporting checks: focused release regressions passed, transcript evals passed, memory-dedupe
  dry-run was clean, and ClaudeViv review confirmed the overall FAIL classification.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MEMHARD-001` | PARTIAL | Latest 03:00 hardener apply exited 0 and updated `world` / `moments`, but transcript vectors deferred. | Saved-memory apply passed; transcript vector sub-lane failed. |
| `MEMHARD-002` | PASS | Report and case updates use sanitized counts, timestamps, status fields, and feature identifiers. | Raw runtime, browser, DB, and transcript evidence omitted. |
| `MTM-006` | BLOCKED | RAG/vector health endpoints unavailable. | Browser transcript-recall signoff was not attempted. |
| `MTM-013` | PARTIAL | Latest hardener run recorded 46 vector-presence check failures and avoided destructive repair. | Requires healthy RAG and zero vector-presence errors. |
| `MTM-017` | PARTIAL | Current run had no new cap skips, but aggregate transcript state still had 3 deferred-cap files. | Caught-up status is not proven. |
| `RAG-001` | FAIL | Configured RAG API refused health checks; no RAG/PGVector container was running. | Conversation/meeting recall vector path unavailable. |
| `SCHED-002` | FAIL | Scheduler was healthy, but the 03:00 Workbench task terminally failed. | The delivery ledger advanced to failure instead of success. |
| `PW-029` | FAIL | Playwright showed Workbench reachable and schedule visible; DB run row failed with a GlassHive dispatch `HTTP 404` class. | Source tests passed, but scheduled user flow failed. |
| `MEMCONT-001` | BLOCKED/PARTIAL | Continuity capture skipped Mongo because generated `MONGO_URI` was blank; direct sanitized Mongo queries compensated for this audit only. | Reusable audit remains incomplete. |

## Traceability

- Feature: Viventium overnight routines QA.
- Requirement: `docs/requirements_and_learnings/20_Memory_System.md`,
  `docs/requirements_and_learnings/11_Scheduling_Cortex.md`,
  `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`,
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`, and
  `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`.
- Use case: verify scheduled memory hardening, transcript ingest/RAG lifecycle, Workbench scheduled
  deep-thought routine, scheduler state, prompt/eval surface, and helper/manual-ingest state after
  the nightly window.
- QA case: `MEMHARD-001`, `MEMHARD-002`, `MTM-006`, `MTM-013`, `MTM-017`, `RAG-001`,
  `SCHED-002`, `PW-029`, `MEMCONT-001`, and `MEMCONT-002`.
- Expected result: scheduled jobs advance, vector/RAG lifecycle is current or honestly deferred,
  Workbench/Scheduler user surfaces are reachable, and evidence is public-safe.
- Actual evidence: memory LaunchAgent fired and Scheduler/Workbench were reachable, but RAG/vector
  was unavailable and the Workbench/GlassHive run failed.
- Remaining gap or fix: repair RAG/Ollama supervision and GlassHive scheduled dispatch, then rerun
  transcript vector presence checks and a synthetic schedule delivery proof.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Overnight routines across memory, transcript RAG, Scheduling Cortex, Prompt Workbench, and memory continuity. |
| Code owning path | Which code path owns the behavior? | Memory hardener wrapper, Scheduling Cortex SQLite loop, Prompt Workbench service, GlassHive dispatch, RAG/vector sidecar, generated runtime env. |
| Docs and nested docs | Which docs define expected behavior? | Required docs listed in Traceability plus owning QA cases. |
| Logs | Which sanitized logs confirm or contradict the result? | Memory hardening logs showed vector-presence errors; startup logs showed local embeddings runtime unavailable; helper logs showed no manual ingest. |
| DB/state/persistence | Which sanitized state confirms it? | Memory run summary, scheduler DB counts/timestamps, scheduled-prompt run row, Mongo counts, continuity capture warning. |
| Generated/shipped artifact | Which generated config was inspected? | Generated runtime env showed memory hardening enabled, transcript RAG mode configured, local embeddings selected, scheduler port set, and Prompt Workbench not stack-managed. |
| Real user path | Which user path was exercised? | Playwright opened Prompt Workbench and selected the built-in Workbench schedule. |
| Visible UX comparison | Did visible state match supporting evidence? | Yes: the Workbench UI was reachable and showed the schedule enabled for the next 03:00 run; DB showed the current run failed. |
| Not run / blocked | Which required surface was not run? | Browser transcript recall, exact-model Workbench eval, scheduler restart, GlassHive rerun, manual ingest, and owner-memory inspection were not run in this read-only audit. |

## User-Grade Evidence

- Surface exercised: Playwright browser, CLI status, scheduler health, memory hardener status,
  read-only DB/log inspection, and generated-config inspection.
- Real user path: opened Prompt Workbench in a real browser and selected `Subconscious Deep Thought`.
- Visible outcome: the Workbench UI loaded, showed Scheduled Prompts, showed the selected schedule
  enabled, and showed the next 03:00 local run.
- Expanded/detail state: the selected schedule detail showed the GlassHive host execution route; raw
  private folder/path text from that detail view was not copied into this report.
- Persistence/reload result: no schedule or memory state was changed by the audit; persisted
  scheduler rows showed the 2026-05-27 run failed and the next run advanced.
- Backend/log/DB confirmation: scheduler health was OK; latest scheduled-prompt run failed with a
  GlassHive dispatch `HTTP 404` class; hardener summary recorded `vector_runtime_unreachable`.
- Final model/runtime wording check: no model answer was generated in the audit; visible Workbench
  state and DB state both indicated scheduled execution existed but failed downstream.
- Substitution check: source tests, logs, and DB rows supported the result, but did not replace the
  blocked browser transcript-recall check or the failed Workbench schedule outcome.

## Expected Overnight Routines

- Saved-memory hardening: daily `0 3 * * *` local LaunchAgent, apply mode, full 7-day lookback,
  Anthropic primary model with fallbacks, and transcript ingest enabled.
- Meeting transcript lane: configured transcript source, sidecar ignore glob, summary-only RAG mode,
  vector presence checks, and current summary/inventory artifact lifecycle.
- Prompt Workbench scheduled prompt: enabled **Subconscious Deep Thought** Workbench-private schedule
  due daily at 03:00 local through Scheduling Cortex and GlassHive host execution.
- User-level scheduled routines: active Scheduling Cortex rows should advance due schedules and
  write delivery ledger state, with failures classified instead of silently stalling.
- Prompt Workbench evals: no-live and exact-model eval artifacts should remain inspectable; no-live
  previews are not model-performance claims.
- Status-bar/helper manual ingest: helper state should not imply a completed manual ingest when no
  user-triggered ingest ran.

## Actual Results

- Saved-memory hardening **ran** at the expected 03:00 local schedule. The latest run started at
  2026-05-27T10:00:03Z, finished at 2026-05-27T10:03:10Z, exited successfully, and used
  `anthropic / claude-opus-4-7 / xhigh`.
- The hardener fed the complete 7-day lookback: 422 messages from 56 conversations, 0 omitted for
  input cap, 1 successful model attempt, and 0 model-attempt failures.
- The hardener applied validated changes to two generic saved-memory keys, `world` and `moments`.
  Sanitized Mongo state confirmed matching key update timestamps; raw values were not inspected for
  public evidence.
- Transcript/RAG work **did not complete**. The hardener recorded 46 vector-presence check failures,
  `transcript_vectors.deferred=true`, and `reason=vector_runtime_unreachable`.
- The latest hardener uploaded 0 transcript vectors and deleted 0 stale vectors. Aggregate transcript
  state still reports 3 files deferred by cap.
- RAG/vector health was unavailable: the configured RAG API refused health checks, no RAG/PGVector
  container was running, and the local embeddings server was not listening even though the configured
  model artifact exists.
- Scheduling Cortex was listening and returned a healthy public-safe runtime identity.
- The active Workbench nightly task did run and advanced to the next day, but its 2026-05-27 run row
  failed immediately with a GlassHive dispatch `HTTP 404` class.
- User-level agent schedules were not overdue at the audit time, but 9 active rows still carried
  prior `missed` status/outcome and need a separate executor-health follow-up.
- Prompt Workbench was reachable in Playwright and via its health endpoint, but no new no-live or
  exact-model eval artifact was produced or inspected during this read-only audit.
- The status-bar helper was running. Manual transcript ingest logs showed no user-triggered ingest
  after 2026-05-15, and no manual ingest was triggered during this audit.

## Evidence Checked

- LaunchAgent/plist state: memory hardening installed, loaded, 03:00 local calendar, direct
  `env -i` wrapper invocation, App Support working directory, and last exit code 0.
- Generated runtime config: memory hardening enabled, transcript source configured,
  `detailed_summary_only` transcript RAG mode, local embeddings selected for RAG, scheduler port set,
  and stack-managed Prompt Workbench disabled.
- Memory hardening state: latest run `20260527T100003Z`, apply mode, full lookback, two generic
  changed keys, no input clipping, and redacted vector-presence error telemetry.
- Runtime probes: Scheduler and Workbench healthy; RAG/vector and local embeddings endpoints
  unavailable.
- Scheduler SQLite summaries: 14 scheduled tasks, 11 active, 0 active overdue, 9 active rows carrying
  prior missed state, 1 active Workbench/GlassHive row that failed at the 03:00 run and advanced to
  the next day.
- Mongo read-only summaries: saved-memory, message, conversation, meeting-transcript file rows, and
  vector-backed file rows were present; meeting-transcript file rows were stale relative to the
  current hardener run because RAG was unavailable.
- Continuity audit capture: returned `warning`; Mongo introspection was skipped because generated
  runtime `MONGO_URI` is blank.
- Playwright CLI: opened Prompt Workbench, verified the visible schedule and execution-route surface,
  and did not publish the raw snapshot because it contained private runtime text.
- Git drift: parent repo already contained unrelated background-agent/GlassHive edits before this
  report; those were not changed or claimed by this audit.

## Automated Evidence

- `bin/viventium status`: core web/API surfaces reachable, Conversation Recall still starting,
  Workbench standalone.
- `bin/viventium memory-harden status`: latest scheduled run succeeded; aggregate transcript state
  still has processed and deferred-cap entries.
- Local endpoint probes: Scheduler and Workbench health OK; RAG/vector and local embeddings health
  unavailable.
- Sanitized SQLite queries over Scheduling Cortex state: confirmed the failed Workbench run row, next
  run advancement, and carried prior missed status on user-level rows.
- Sanitized Mongo queries over the local native DB: confirmed continuity surfaces exist while
  vector-backed meeting-transcript rows did not update during the current hardener run.
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
- Playwright CLI Workbench open + snapshot: passed for reachability and visible schedule inspection;
  raw snapshot retained as local-only evidence.

## Status By Goal

| Goal | Status | Evidence |
| --- | --- | --- |
| Memory hardening scheduled apply | **PARTIAL** | LaunchAgent fired and saved-memory apply succeeded, but transcript vector sub-lane failed in the same run. |
| Transcript ingest/catch-up | **FAIL / PARTIAL** | 46 vector-presence checks failed, 0 vectors uploaded/deleted, and 3 aggregate deferred-cap files remain. |
| Transcript summary/RAG artifacts | **FAIL** | RAG/vector runtime unavailable; existing vector-backed rows stale relative to the current hardener run. |
| Prompt Workbench scheduled deep-thought routine | **FAIL** | 03:00 local Workbench task ran and advanced, but terminally failed with GlassHive dispatch `HTTP 404`. |
| User-level scheduler routines | **PARTIAL** | No active row was overdue at audit time, but 9 active rows carried prior `missed` state/outcome. |
| Prompt Workbench eval artifacts | **NOT RUN** | Source tests passed and Workbench was reachable, but no no-live or exact-model eval artifact was produced or inspected tonight. |
| Scheduler/LaunchAgent state | **PARTIAL** | Memory LaunchAgent and Scheduler health passed; downstream Workbench/GlassHive delivery failed. |
| Model/provider/fallback telemetry | **PASS** | Anthropic probe succeeded; selected provider/model/effort visible; no model-attempt failures recorded. |
| Status-bar/manual-ingest state | **NOT RUN** | Helper was running, but no manual ingest ran recently and none was triggered in this audit. |
| Public/private safety | **PASS** | Report uses sanitized counts, timestamps, statuses, and feature identifiers only. |

## Findings

1. **P1: Workbench/GlassHive nightly routine ran but failed.**
   Scheduler is no longer the immediate blocker: the 03:00 row advanced and wrote a terminal failed
   run. The failure is now downstream GlassHive dispatch returning an `HTTP 404` class from the
   find-or-resume path.

2. **P1: Transcript RAG/vector runtime is unavailable.**
   RAG health checks failed, no RAG/PGVector container was running, the configured local embeddings
   server was not listening, and the hardener recorded 46 vector-presence errors.

3. **P2: Transcript lifecycle remains partial despite a successful saved-memory apply.**
   The hardener updated saved-memory keys, but uploaded 0 vectors and left aggregate transcript state
   with 3 deferred-cap files.

4. **P2: Continuity audit cannot introspect Mongo from generated runtime env.**
   The capture warned that Mongo was skipped because `MONGO_URI` is blank. Direct sanitized Mongo
   queries compensated for this audit, but the reusable audit remains incomplete.

5. **P2: User-level schedules still carry prior missed state.**
   They were not overdue at audit time, but 9 active rows retained `missed` status/outcome and should
   be reconciled instead of allowed to blend into future nightly checks.

6. **P3: Manual ingest/eval surfaces had no fresh run.**
   Helper was running and Workbench was reachable, but no manual transcript ingest or Workbench eval
   artifact was generated in this read-only audit.

## ClaudeViv Review

ClaudeViv review-only JSON completed after the evidence pass. It confirmed the overall **FAIL**
classification and the main blockers: saved-memory apply succeeded only for the saved-memory lane,
transcript vector/RAG failed, Workbench scheduled delivery failed terminally, continuity audit remains
degraded, and raw Workbench/LaunchAgent evidence must stay local-only.

Adjustments incorporated from ClaudeViv:

- Overall nightly status remains **FAIL**, not partial pass.
- Memory hardening is **PARTIAL** at the goal level because the transcript vector sub-lane failed.
- Transcript summary/RAG artifacts are **FAIL**, not partial, while RAG/Ollama is unavailable.
- Workbench eval artifacts are **NOT RUN** because no fresh no-live or exact-model eval artifact was
  produced or inspected tonight.
- User-level scheduler routines are **PARTIAL** because prior missed state remains on active rows.
- Status-bar/manual-ingest state is **NOT RUN** because no manual ingest was triggered.
- Next remediation should classify the GlassHive `HTTP 404` root cause before rerunning a schedule.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private prompts, private chats, raw transcripts, customer data, personal emails, or
  screenshots with private content.
- [x] No account identifiers, conversation IDs, message IDs, session/call IDs, Telegram chat IDs,
  Mongo `_id` values, raw provider request/response IDs, or raw worker/project identifiers.
- [x] No local absolute home paths, hostnames, machine names, stack traces with private paths,
  database exports, App Support dumps, or raw runtime dumps.
- [x] Raw Playwright snapshot text, Workbench API payloads, LaunchAgent plist values, and private
  paths observed during audit were kept out of this public report.
- [x] Private evidence is summarized only with sanitized counts, timestamps, statuses, and feature
  identifiers.

## Not Run

- No memory hardening apply/dry-run, transcript ingest, scheduler restart, stack restart, Workbench
  manual run, GlassHive worker run, no-live eval, exact-model eval, or manual transcript ingest was
  triggered.
- No authenticated LibreChat browser memory/recall prompt was sent.
- No owner memory, conversation, transcript, or schedule state was intentionally mutated as part of
  this audit.

## Recommended Next Actions

1. Repair RAG/Ollama supervision through the supported runtime path, then verify RAG `/health`,
   vector presence checks, and local embeddings readiness without relying on a one-off manual
   `ollama serve`.
2. Classify the GlassHive dispatch `HTTP 404`: stale stored project/worker id, worker unavailable at
   03:00, route change, or auth/routing issue. Rerun only with operator-approved synthetic schedule
   proof or the next 03:00 window.
3. After RAG is healthy, rerun or wait for bounded transcript catch-up until
   `vector_presence_error_count=0`, no `vector_runtime_unreachable`, and aggregate deferred-cap
   backlog is cleared or intentionally explained.
4. Fix or extend `continuity_audit.py` so local Mongo continuity can be inspected when generated
   `MONGO_URI` is intentionally blank.
5. Reconcile the 9 active user-level schedules carrying prior missed state.
6. Confirm helper transcript-ingest log rotation/authority before treating 2026-05-15 as the final
   manual-ingest date in future audits.
