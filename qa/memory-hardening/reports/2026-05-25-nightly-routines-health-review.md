<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-25 Nightly Routines Health Review

Status: **FAIL / PARTIAL** for the overnight-routine contract.

Run time: 2026-05-25 04:01-04:08 local time, after the documented 03:00 local
memory-hardening and Workbench deep-thought schedules should have completed.

This report is public-safe. Raw App Support logs, schedule prompts, memory values, transcript
content, account emails, local absolute paths, DB ids, launch tokens, screenshots, and secret-bearing
environment values were not copied here. The raw `launchctl` inspection exposed inherited
environment metadata that can contain secrets; it is intentionally summarized only.

## Expected Overnight Routines

- Saved-memory hardening: enabled generated runtime config, daily schedule `0 3 * * *`, apply mode,
  full 7-day lookback, launch-ready Anthropic primary model with fallbacks, and transcript ingest
  enabled.
- Meeting transcript lane: source folder configured, ignore glob for sidecar bookkeeping, default
  `detailed_summary_only` RAG mode, processed-content freshness, vector presence checks, and
  summary/inventory artifact lifecycle.
- Prompt Workbench scheduled prompt: enabled **Subconscious Deep Thought** Workbench-private
  schedule due daily at 03:00 America/Los_Angeles through Scheduling Cortex and GlassHive host
  execution.
- User-level scheduled routines: active Scheduling Cortex rows should advance due schedules and
  write delivery ledger state, with failures classified instead of silently stalling.
- Prompt Workbench evals: recent eval artifacts should remain inspectable; no-live previews are not
  model-performance claims.

## Actual Results

- Saved-memory hardening **ran successfully** on 2026-05-25 at the expected 03:00 local schedule.
  The latest run started at 2026-05-25T10:00:07Z, finished at 2026-05-25T10:32:05Z, applied one
  validated `moments` update for one hashed user, and the saved-memory DB timestamp matched the run
  finish time.
- The memory-hardening LaunchAgent is installed, loaded, scheduled for 03:00 local, exits cleanly,
  invokes the wrapper directly through `env -i`, and uses App Support as its working directory.
- The latest hardener run completed a full 7-day lookback: 456 messages from 50 conversations, 0
  omitted for input-cap reasons, and memory instructions present.
- Transcript vector-auth errors from the prior run were cleared: `vector_presence_error_count=0`.
  The run requeued 23 transcript artifacts with missing vectors, processed 20 files, uploaded 20
  summaries plus one inventory artifact, and left 3 files deferred by the per-run cap.
- Transcript summary/RAG state is therefore **PARTIAL**, not pass: the vector repair/backfill still
  has 3 capped files outstanding, and transcript summarization recorded 3 model-attempt failures
  before completing the run.
- Mongo read-only summaries showed 35 `meeting_transcript` vector-backed file rows, latest update at
  the hardener finish time, and one `conversation_recall` vector-backed row updated earlier the same
  morning.
- RAG `/health` returned `UP`; unauthenticated `/status` returned `401` as expected; OpenAPI paths
  included `/documents/exists`, `/query`, and `/query_multiple`.
- Prompt bundle drift was clean: source/live bundle hashes matched, prompt count was 66, and memory
  prompt bundle entries were present for the hardener, transcript caveat, and transcript summarizer.
- Local-prod Scheduling Cortex is still **failed/stale**. The process answering `localhost:7110`
  belongs to a separate dev-env scheduler PID file, while the local-prod scheduler PID is stale and
  the local-prod scheduler log stopped on 2026-05-23.
- The local-prod scheduler DB had 10 active tasks, 9 overdue active tasks, and latest task
  run/update at 2026-05-23T10:00:18Z.
- The Workbench **Subconscious Deep Thought** schedule still showed last failure from
  2026-05-23 with a connection-refused `URLError`, `next_run_at=2026-05-24T10:00:00Z`, and no
  2026-05-24 or 2026-05-25 local-prod run rows.
- A real Playwright browser snapshot of Prompt Workbench confirmed the user-visible stale state:
  scheduled prompt objects loaded, **Subconscious Deep Thought** was enabled but still due
  "May 24, 3:00 AM", and another user-level schedule was visibly due in the past. The raw snapshot
  contained private-looking schedule text and is not copied here.
- Prompt Workbench itself is running standalone on loopback and healthy, but generated runtime has
  `START_PROMPT_WORKBENCH=false`, so this is not stack-managed evidence.
- Prompt Workbench eval artifacts remain inspectable, but the current eval lane is **PARTIAL**:
  latest no-live preview artifacts are from 2026-05-22, and latest exact-model artifacts found from
  2026-05-21 include blocked or failed-completion statuses.
- Status-bar helper was running. Manual transcript ingest was not triggered because this audit was
  read-only.

## Commands And Checks Run

- `bin/viventium status`: local product runtime reported ready; core browser/API/Telegram/recall/RAG
  and local web-search surfaces were reachable or configured.
- `bin/viventium memory-harden status`: latest run `20260525T100007Z`, apply, success; aggregate
  transcript state showed processed and deferred-cap entries.
- LaunchAgent/plist inspection: memory hardening installed, loaded, 03:00 local schedule, direct
  wrapper invocation, last exit code 0. Raw secret-bearing inherited environment metadata was
  redacted from this report.
- Generated runtime env and prompt bundle inspection: memory hardening enabled, transcript source
  set, RAG embeddings configured for Ollama, scheduler URL set to local port 7110, Workbench not
  stack-managed, prompt drift count 0.
- SQLite read-only scheduler inspection: local-prod DB stale/overdue; dev-env DB separate and
  active enough to mask local-prod scheduler health when checking only port 7110.
- Mongo read-only inspection: sanitized counts for files, saved memories, meeting transcript rows,
  conversation recall rows, and listen-only message count.
- RAG health/API-shape checks: `/health` passed; `/status` required auth; document/query endpoints
  were present.
- Playwright CLI: loaded Prompt Workbench and captured a DOM snapshot confirming visible stale
  scheduled-prompt state.
- Continuity audit:
  `python3 scripts/viventium/continuity_audit.py capture ...` returned `warning`, with schedules
  latest timestamp 2026-05-23T10:00:18Z. Mongo introspection was skipped by that script because it
  did not derive the local Mongo URI from generated local Mongo variables; direct sanitized Mongo
  queries compensated for this audit.
- Automated regression/eval checks:
  - `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi python -m pytest tests/release/test_memory_hardening_contract.py tests/release/test_config_compiler.py tests/release/test_scheduling_mcp_supervision.py tests/release/test_prompt_workbench.py -q`
    passed: 191 passed, 16 skipped.
  - `node qa/meeting-transcript-memory/evals/run-evals.cjs` passed: 12 passed, 0 failed.
  - `bin/viventium memory-dedupe --dry-run --json` passed read-only: 0 duplicate memory groups,
    0 duplicate key groups, 0 deletes, no index creation.

## Status By Goal

| Goal | Status | Evidence |
| --- | --- | --- |
| Memory hardening scheduled apply | **PASS** | LaunchAgent loaded and latest scheduled apply succeeded at 03:00 local with one validated key update. |
| Transcript ingest/catch-up | **PARTIAL** | Vector auth errors cleared and 20 files processed; 3 files remain deferred by per-run cap. |
| Transcript summary/RAG artifacts | **PARTIAL** | RAG and DB rows are current, but capped vector repair remains incomplete and 3 model attempts failed before completion. |
| Prompt Workbench scheduled deep-thought routine | **FAIL** | Latest local-prod run failed on 2026-05-23; no 2026-05-24/25 run rows; UI still shows stale due date. |
| User-level scheduler routines | **FAIL** | Local-prod scheduler DB has 9 overdue active tasks and no updates since 2026-05-23. |
| Prompt Workbench eval artifacts | **PARTIAL** | No-live previews inspectable; latest exact-model artifacts are stale and include blocked/failed-completion statuses. |
| Scheduler/LaunchAgent state | **FAIL** | Memory LaunchAgent healthy, but user-visible Scheduling Cortex path is broken and cross-wired to a dev env. |
| Model/provider/fallback telemetry | **PARTIAL** | Fallback telemetry is present; Anthropic probes timed out, OpenAI probe succeeded, and top-level provider/model wording differs from per-user consolidation telemetry. |
| Status-bar/manual-ingest state | **NOT RUN** | Helper was running, but manual ingest was not triggered in this read-only audit. |
| Public/private safety | **PASS with warning** | Report uses sanitized counts/timestamps/statuses only; raw launchctl and browser evidence were not copied. |

## Findings

1. **P1: Local-prod Scheduling Cortex remains failed and masked by a dev env.**
   `localhost:7110` is healthy, but it is owned by a separate dev-env scheduler. The
   local-prod scheduler child is stale, its log stopped on 2026-05-23, and its DB has 9 overdue
   active tasks.

2. **P1: Workbench deep-thought routine is not delivering.**
   The Workbench-private nightly schedule has no fresh local-prod run after the 2026-05-23
   connection-refused failure and remains visibly overdue in Prompt Workbench.

3. **P2: Transcript vector repair is progressing but incomplete.**
   The latest run fixed the prior vector-auth degradation and uploaded summaries/inventory, but 3
   requeued files remain deferred by cap. This is expected bounded behavior, but the lane is not
   caught up.

4. **P2: Provider/model telemetry is potentially confusing.**
   The top-level run summary reports OpenAI GPT-5.5 after advisory probe fallback, while per-user
   hardener telemetry reports Anthropic `opus` as the consolidation model. The report treats this as
   partial until the hardener output makes that distinction explicit.

5. **P2: Continuity audit misses local Mongo without fallback URI derivation.**
   The continuity audit captured stale scheduler state but skipped Mongo because generated local
   Mongo variables were not converted into a connection URI. Direct sanitized Mongo queries filled
   the gap for this audit.

6. **P2: Nested LibreChat working tree is dirty.**
   The parent repo is clean and the parent pin matches the nested LibreChat HEAD, but the nested
   working tree has local modifications in agent runtime/seed scripts and tests. Clean-checkout
   reproducibility is not proven for those local changes.

## ClaudeViv Review

ClaudeViv review-only JSON completed after the evidence pass. It confirmed the main findings:
memory hardening ran successfully, local-prod scheduler remains cross-wired to the dev env, the
Workbench deep-thought schedule has not recovered, transcript vector repair is partial, and raw
launchctl/browser evidence must stay out of public artifacts.

Adjustments incorporated from ClaudeViv:

- Transcript summary/RAG artifacts are marked **PARTIAL**, not pass with residual risk, until
  `deferred_cap=0` and vector repair fully catches up.
- Prompt Workbench evals are marked **PARTIAL**, because no-live previews are inspectable but are not
  performance claims and the latest exact-model artifacts are stale/blocked.
- Scheduler/LaunchAgent as a combined goal is marked **FAIL**, because the memory LaunchAgent is
  healthy but the user-visible scheduler path is nonfunctional.
- The provider/model telemetry split is called out explicitly so readers do not infer a single
  selected model from mixed top-level and per-user fields.
- The nested LibreChat dirty tree and continuity-audit Mongo gap are tracked as follow-up risks.

## Not Run

- No memory hardening dry-run/apply, transcript ingest, scheduler restart, dev-env stop, schedule
  manual run, or GlassHive worker run was triggered.
- No authenticated LibreChat browser memory/recall prompt was sent.
- No exact-model live Prompt Workbench eval was started.
- No status-bar manual transcript ingest action was triggered.

## Recommended Next Actions

1. Capture a sanitized pre-repair baseline for `:7110` ownership, local-prod/dev-env PID files, and
   scheduler DB freshness, then stop or move the separate dev-env scheduler off the
   local-prod scheduler port.
2. Restart local-prod Scheduling Cortex and verify process, PID file, DB updates, watchdog
   parent/child state, and log freshness all point to local-prod before crediting recovery.
3. After scheduler ownership is corrected, wait for the next 03:00 scheduled Workbench run or run an
   operator-approved synthetic manual run; verify GlassHive reachability, run ledger, private detail
   pointer, and public-safe result summary.
4. Clear the transcript backlog only with operator approval, using the bounded caught-up ingest path
   or the next scheduled batch. Acceptance requires `deferred_cap=0`, completed vector uploads, and
   no vector-presence errors.
5. Reconcile hardener provider/model telemetry so top-level probe/fallback selection and per-user
   consolidation model selection are named distinctly in future summaries.
6. Fix `continuity_audit.py` capture mode so it derives the local Mongo URI from generated local
   Mongo variables when `MONGO_URI` is intentionally blank.
7. Resolve or intentionally park the nested LibreChat dirty working tree before claiming clean
   checkout reproducibility for nightly behavior.
