<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-31 Nightly Routines Health Review

Overall status: PARTIAL

Audit window: 2026-05-31 04:03-04:23 PDT, after the documented 03:00 local overnight jobs.

This report is public-safe. Raw LaunchAgent output, browser snapshots, prompt text, transcript text,
account identifiers, runtime tokens, local absolute paths, callback payloads, proposal actions, and
private detail files were inspected locally but are not copied here. Temporary Playwright snapshot
files created during the audit were removed.

## Expected And Actual Routines

| Routine | Expected | Actual | Status |
| --- | --- | --- | --- |
| Memory hardening LaunchAgent | Fire at 03:00 local and complete bounded model-backed memory hardening if eligible data exists. | Fired at 03:00 local, exited 0, model probe succeeded, and the hardener finished quickly with zero eligible users selected. | PARTIAL/SKIPPED |
| Transcript ingest and catch-up | Process pending transcript summaries and vector/RAG lifecycle work when eligible. | Transcript indexes remained fully processed from prior runs, but today's hardener selected zero users and performed no transcript scan or vector lifecycle work. | PARTIAL/SKIPPED |
| Transcript summary/RAG artifacts | Keep RAG services healthy and transcript artifacts usable for recall. | RAG API, vector DB, embeddings model, and related services were healthy; no browser chat recall answer was run in this audit. | PARTIAL |
| Scheduled Workbench deep-thought routine | Run the built-in 03:00 Workbench schedule through Scheduling Cortex and GlassHive. | Latest scheduled run completed through GlassHive, parent task ledger reported success/sent, callbacks delivered, and Workbench visibly showed the completed recent run. | PASS |
| Prompt benchmark/workbench evals | Run only if a scheduled eval lane is declared. | Built-in nightly Workbench schedule has no eval family/mode declared, and no fresh exact-model eval run was expected. | NOT RUN/N/A |
| Scheduler state and callback health | Scheduler should be attached to the active runtime, with no active callback backlog or fresh dead-letter. | Scheduler health matched the active runtime identity shape; GlassHive metrics showed no queued/active runs, no pending callback backlog, and no fresh dead-letter for the 03:00 run. | PASS |
| Model/provider/fallback telemetry | Preserve provider/model evidence and surface stale auth failures honestly. | Memory hardener recorded provider/model/probe success. Several user-level schedules still carried stale prior-day auth or mapping failures and were due later than this audit window. | PARTIAL |
| Status-bar/manual ingest state | Record any overnight manual-ingest/helper state changes. | No recent helper manual transcript-ingest activity was found; helper logs only showed normal healthy-stack auto-start checks. | NOT CHANGED |
| Power and heat budget | Do not force expensive work while on battery or thermally constrained. | Machine was on AC power with full battery and no thermal/performance warning. No power or idle gate override was used. | PASS |

## Evidence Checked

- Project docs and QA contracts: `AGENTS.md`, key principles, memory system, installer/config
  compiler, runtime feature QA map, scheduler, prompt architecture, stable runtime, `qa/README.md`,
  feature checklist, and the relevant memory, transcript, RAG, Workbench, scheduler, and continuity
  cases.
- Runtime readiness: public CLI status and dev-runtime status both showed the active local runtime
  stack healthy, including LibreChat, Modern Playground, Telegram services, Conversation Recall,
  SearXNG, Firecrawl, Google Workspace MCP, Microsoft 365 MCP, and the macOS helper.
- Power state: AC power, charged battery, and no thermal or performance warning.
- LaunchAgent: `ai.viventium.memory-harden` was loaded, had the 03:00 event trigger, and reported
  last exit code 0. Raw output included private inherited environment data and was not retained in
  the public report.
- Memory hardening status: latest 03:00 run finished successfully with provider/model telemetry and
  a successful model probe, but selected `user_count=0` and produced no apply results. A local DB
  eligibility check found the configured operator account but not eligible for memory hardening; the
  exact account values are intentionally omitted.
- Transcript state: aggregate transcript indexes showed 3 indexes and 47 processed files. Local
  transcript-like artifact rows were present, but no new files were scanned in the latest hardener
  run.
- RAG/vector health: RAG health returned `UP`; vector DB, RAG API, Firecrawl, SearXNG, and the local
  embedding model were available.
- Scheduler state: scheduler `/health` returned `ok` with runtime identity fields present. The
  latest built-in Workbench run completed at the 03:00 due time and advanced the parent delivery
  ledger to success/sent.
- GlassHive state: latest Workbench run completed with no run error, callback rows for the new run
  delivered, no active callback backlog existed, and only historical terminal dead-letter audit rows
  remained.
- Prompt Workbench UI: Playwright opened the authenticated local Workbench, selected the built-in
  scheduled prompt, and verified the schedule enabled state, next 03:00 run time, latest completed
  run, and a private proposal artifact summary without publishing private prompt/result content.
- Continuity: continuity audit returned `ok` with no checks listed. The unsupported JSON flag was
  noted separately; the plain read-only audit path was used.
- Helper/manual ingest: helper manual-ingest logs showed no recent overnight manual ingest change.
- Git drift: parent and nested component worktrees already had unrelated dirty/untracked changes.
  This audit did not revert them.

## Commands And Checks Run

| Check | Result |
| --- | --- |
| `bin/viventium status` | PASS, local runtime ready. |
| `bin/viventium dev-runtime status` | PASS, command/helper/live stack checkouts aligned. |
| `bin/viventium memory-harden status --json` | PARTIAL, latest run success with zero eligible users and no transcript work. |
| Sanitized Mongo eligibility/transcript queries | PARTIAL, configured operator account present but not eligible; transcript artifacts present. |
| RAG, SearXNG, Firecrawl, Docker, and embedding health probes | PASS, required services available. |
| Scheduler health and SQLite status queries | PASS for 03:00 Workbench run; stale prior-day user-level failures remain for later schedules. |
| GlassHive health, metrics, and callback DB status | PASS for latest 03:00 run; no fresh active callback backlog. |
| `bin/viventium prompt-workbench status --json` and Workbench `/api/health` | PASS, Workbench running and healthy; token omitted. |
| Playwright Workbench UI inspection | PASS for visible schedule/run history; private snapshots deleted. |
| `bin/viventium continuity-audit` | PASS, returned `ok`; `--json` is not supported by this command. |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | PASS, 12 passed, 0 failed. |
| `bin/viventium memory-dedupe --dry-run --json` | PASS, 0 duplicate groups, 0 docs, 0 deleted, no index creation. |
| Focused release pytest with `uv run --with pytest --with pyyaml --with 'pydantic>=2' --with croniter ...` | PASS, 125 passed, 21 skipped. Initial direct pytest collection showed missing local `croniter`, then the dependency-explicit run passed. |
| `uv run --with pytest --with pyyaml --with 'pydantic>=2' --with croniter python -m pytest tests/release/test_qa_results_public_safety.py -q` | PASS, 1 passed after this report and case updates were written. |
| Public-safety grep and `git diff --check` on touched QA files | PASS, no private data hits in the new report and no whitespace errors. |

## Case Status

| Case | Status | Evidence |
| --- | --- | --- |
| `MEMHARD-001` | PARTIAL/SKIPPED | LaunchAgent and model probe passed, but zero eligible users meant no memory apply, transcript scan, or vector lifecycle occurred. |
| `MEMHARD-002` | PASS | This report is sanitized and omits private logs, tokens, prompts, browser snapshots, paths, and identifiers. |
| `MEMHARD-003` | PASS | Audit observed AC power and no thermal/performance warning; no override flags were used. |
| `SCHED-002` | PASS | 03:00 Workbench schedule completed, and parent ledger matched success/sent. |
| `SCHED-006` | PASS | Terminal GlassHive callback and parent task ledger agreed for the latest completed run. |
| `SCHED-009` | PASS | Latest callback delivery had no active backlog or fresh dead-letter. |
| `PW-029` | PASS | Workbench UI showed the enabled built-in schedule, next 03:00 run, latest completed run, and private proposal summary. |
| `MTM-006` | PARTIAL | RAG/vector health is green, but today's hardener did not rescan transcript vectors and browser recall was not rerun. |
| `RAG-001` | PARTIAL | Supporting RAG/embedding/vector health passed; grounded browser chat recall remains unproven today. |
| `MEMCONT-001` | PASS for continuity audit, PARTIAL for visible recall | Continuity audit returned `ok`; browser recall/continuity UX was not rerun. |

## Stale, Skipped, Failed, Or Degraded Items

1. Memory hardening is the main degraded result. The scheduler process and model path worked, but
   the configured operator account was not eligible for memory hardening at audit time, so the 03:00
   run became an empty success. Treat this as PARTIAL/SKIPPED until the operator confirms whether
   that opt-out is intentional.
2. Transcript catch-up and vector lifecycle did not run today because the hardener selected zero
   users. Prior transcript indexes still show all known files processed.
3. Browser conversation recall and transcript-RAG answer grounding were not exercised today. Service
   health is supporting evidence only, not user-path signoff.
4. Several user-level scheduled tasks still carry stale prior-day failures for connected-account or
   mapping prerequisites. They were not due during this 04:00 local audit window and need a follow-up
   check after their next due time.
5. No prompt eval lane is declared on the built-in nightly Workbench schedule, so no fresh exact-model
   eval run was expected. Add an eval lane explicitly if nightly prompt benchmarking is required.

## ClaudeViv Review

ClaudeViv was run review-only after evidence collection, with no tools and no repo/runtime changes.
It agreed with the overall PARTIAL classification at high confidence.

Confirmed by ClaudeViv:

- The Workbench 03:00 tick, scheduler ledger, GlassHive completion, and callback delivery are a
  real PASS.
- The memory hardener should not be marked PASS because `user_count=0` means the substantive memory
  and transcript work did not run.
- Power, runtime, RAG service, continuity, and focused test evidence support the audit but do not
  replace missing browser recall evidence.
- Public-safety handling was appropriate as long as raw launch output, browser snapshots, prompt
  content, account identifiers, raw run ids, callback payloads, and local paths stay out of the repo.

ClaudeViv unresolved risks:

- Confirm whether the operator account's current memory-hardening ineligibility is intentional.
- Add a small browser conversation-recall/transcript-RAG check to a future nightly review when safe.
- Follow up after the later user-level schedule due times to determine whether stale auth/mapping
  failures recover or remain actionable.

## Next Actions

1. Ask the operator whether the configured account should remain ineligible for memory hardening. Do
   not change memory eligibility or owner memories as part of this read-only audit.
2. After confirmation, either document the skip as expected or repair the eligibility/config path and
   let the next scheduled run prove a non-empty memory/transcript pass.
3. Run a public-safe browser recall check in a future audit before claiming transcript/RAG user-path
   PASS.
4. Recheck user-level scheduled tasks after their next due time and classify any repeated auth or
   mapping failures with concrete fix plans.
