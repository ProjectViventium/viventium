<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-06-03 Nightly Routines Health Review

Overall status: **PARTIAL overall / memory-hardening FAIL; Workbench nightly not due yet at audit
time**.

This was a read-only audit. It did not start model-backed memory apply, transcript ingest,
catch-up, vector rebuild, repair, background-agent work, runtime stops, Docker stops, or owner
memory/conversation mutations. Raw prompts, transcript text, account identifiers, private paths,
tokens, callback payloads, browser snapshots, and rendered Workbench variable payloads stayed out
of the public repo.

## Scope

Docs and QA sources reviewed:

- `AGENTS.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/20_Memory_System.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/02_ARCHITECTURE_OVERVIEW.md`
- `docs/03_SYSTEMS_MAP.md`
- `viventium_v0_4/docs/IMPLEMENTATION_INDEX.md`
- `viventium_v0_4/docs/DEVELOPMENT_GUIDE.md`
- `qa/memory-hardening/cases.md`
- `qa/meeting-transcript-memory/cases.md`
- `qa/memory-continuity/cases.md`
- `qa/prompt-workbench/cases.md`
- `qa/conversation-recall-rag/cases.md`
- `qa/scheduling-cortex/cases.md`
- `qa/installer-resilience/cases.md`

## Power And Safety Gate

| Check | Evidence | Status |
| --- | --- | --- |
| Current power source | AC power, battery charged | `PASS` |
| Thermal state | No current thermal/performance warning | `PASS` |
| Forced overrides | No power/idle override, apply, transcript ingest, repair, rebuild, or background-agent dispatch was run | `PASS` |
| Overnight sleep explanation | Power log showed the machine awake around the 03:00 local hardener window | `PASS` for awake evidence |

No power-budget skip was recorded for today.

## Expected Vs Actual

| Routine | Expected behavior | Actual evidence | Status |
| --- | --- | --- | --- |
| Memory hardening | Launch at configured local `0 3 * * *`, then run scheduled apply if power/idle gates allow it. | Generated runtime and the loaded LaunchAgent both show local 03:00 scheduled apply with dry-run-first enabled and a configured OpenAI/GPT-5.5 route. The machine was awake, but there is no `20260603*` run directory, no stdout/stderr update, no launchd evidence in the queried window, and `memory-harden status` still points to the repaired `20260602T185223Z` run. | `FAIL` |
| Provider/model telemetry | The fresh overnight run proves configured provider/model success or records fallback. | No fresh overnight run exists. The latest repaired scheduled-shaped run used OpenAI/GPT-5.5 directly with one attempt, zero failures, and zero fallback, then was rolled back during QA. That is useful baseline evidence, not today's scheduled run. | `PARTIAL` |
| Transcript ingest/catch-up | Scan configured transcript source and keep summary/RAG artifacts current. | Latest status reports 3 transcript indexes and 47/47 files processed. Latest repaired run saw 26 scoped source entries, 3 ignored sidecars, 0 pending, 0 skipped by cap, 0 requeued missing vectors, and 0 vector-presence errors. No fresh June 3 scheduled scan ran. | `PARTIAL` |
| Transcript summary/RAG artifacts | RAG/vector health must be trustworthy before recall signoff. | RAG `/health` returned `UP`; latest hardener vector telemetry stayed clean. RAG metrics endpoint required auth and returned 401, so no current quantitative vector/corpus counts were proven, and browser chat recall/vector-document proof was not rerun. | `PARTIAL` |
| Workbench nightly reflection | Built-in `Subconscious Deep Thought` schedule dispatches through Scheduler -> GlassHive -> callback -> Workbench. | At audit time, current UTC was before the schedule's next due time. Scheduler DB and Playwright UI both showed the active Workbench private prompt due `2026-06-03T10:00:00Z` / local visible 06:00. Latest completed run remains June 2, completed in about 3m with private proposal artifact summary visible. | `NOT DUE / PARTIAL` |
| Scheduler state | Service health, active ledger, due state, and callback delivery agree. | Scheduler `/health` returned `ok` with hashed runtime identity. DB has 20 tasks, 8 active; the built-in Workbench task is active with last `success` / `sent`. Three orphaned pre-fix rows are inactive. Four active user-level rows still show provider reconnect failures; those are account-action follow-up, not built-in nightly failure. | `PASS/PARTIAL` |
| GlassHive callback outbox | No fresh active callback backlog or retry leak. | Metrics show 0 queued runs, 0 active runs, 0 callback pending, 0 callback delivering, 2 historical dead-letter rows, and active max attempts 0. Latest callback rows are delivered. | `PASS` |
| Prompt benchmark / eval lane | Run relevant no-live/synthetic evals. | Meeting transcript eval bank passed 12/0. Focused release contract suite passed 168/5 skipped through an ephemeral test env. No separate scheduled exact-model eval lane was found, so that lane remains `N/A` rather than proven by these suites. | `PASS` for run suites, `N/A` for separate scheduled exact-model lane |
| Continuity and dedupe | Continuity metadata is current and no duplicate memory/key groups exist. | Continuity audit wrote a metadata-only artifact with status `ok`, no warnings/errors, recall rebuild marker absent, and current generated runtime metadata. Memory dedupe dry-run reported 0 duplicate groups/docs and 0 deletes. Browser recall UX was not rerun. | `PASS/PARTIAL` |
| Status-bar/manual ingest | Manual ingest state should be unchanged unless user-triggered. | Status bar helper is running; no manual transcript ingest was run or changed by this audit. | `PASS/UNCHANGED` |
| Brain readiness/status copy | Live service status and Brain Setup copy should not contradict. | Live services show Primary AI configured, while Brain Setup still says Primary AI needs setup. This is a user-facing status-copy mismatch carried forward from the prior audit. | `PARTIAL` |

## Evidence Checked

- Power source, thermal state, and sleep/wake assertions around the local 03:00 hardening window.
- Generated runtime key presence for memory hardening, provider/model/effort, transcripts, RAG,
  embeddings, GlassHive, Workbench, and Scheduler. Values that identify local state were hashed or
  summarized only.
- Loaded memory-hardening LaunchAgent schedule/shape, log mtimes, run-directory inventory, latest
  status JSON, latest repaired summary, redacted run log, rollback summary, and transcript index
  mtimes/counts.
- Viventium status, active runtime checkout alignment, RAG health, Workbench health, Scheduler
  health, GlassHive metrics, and continuity metadata.
- Sanitized Scheduler SQLite aggregates for task/run status, active rows, built-in Workbench due
  time, and provider-reconnect/account-action rows.
- Sanitized GlassHive SQLite/metrics aggregates for run state and callback outbox health.
- Real-browser Workbench inspection with Playwright: Workbench loaded, sync count showed source/live
  match before selecting the schedule, the built-in schedule was enabled with the expected next run,
  and recent completed run/proposal-action summaries were visible. A detail snapshot exposed private
  rendered-variable text; the temporary snapshot files were deleted and not committed.
- A launchd unified-log query for the memory-hardening label returned no entries in the queried
  post-03:00 window; broader launchd logging may still be needed for root cause.
- Git drift was inspected. The worktree had many pre-existing dirty/untracked files; none were
  reverted. `git diff --check` reported an unrelated trailing-whitespace issue in a GlassHive doc
  diff outside this audit.

## Commands Run

| Command / check | Result |
| --- | --- |
| `pmset -g batt`, `pmset -g therm`, filtered `pmset -g log` | AC power, no current thermal/performance warning, machine awake around 03:00 local. |
| `bin/viventium memory-harden status --json` | Latest run still `20260602T185223Z`; no lock; transcript indexes 47/47 processed. |
| Memory-hardening log/run inventory | No `20260603*` run directory; stdout last updated on June 2, stderr on June 1. |
| LaunchAgent inspection | Loaded direct wrapper schedule at Hour 3 / Minute 0; state not running; no run evidence for today. |
| `bin/viventium status --json` | CLI printed rich status; live core services reachable; Brain Setup Primary AI mismatch remains. |
| `bin/viventium dev-runtime status` | Active runtime checkout, helper checkout, live stack owner, and command checkout all align. |
| Scheduler SQLite queries | Built-in Workbench active and next due `2026-06-03T10:00:00Z`; no June 3 Workbench run yet because not due. |
| GlassHive metrics/SQLite queries | No active/queued runs or callback backlog; two historical dead-letter rows remain bounded. |
| `curl` health checks | RAG `UP`, Workbench `ok`, Scheduler `ok`; RAG metrics returned 401 without auth. |
| `bin/viventium continuity-audit` | Metadata-only continuity artifact status `ok`, no warnings/errors. |
| `bin/viventium memory-dedupe --dry-run --json` | 0 duplicate groups/docs, 0 deletes, no index creation. |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | 12 passed, 0 failed. |
| Focused `uv run ... pytest ...` suite | 168 passed, 5 skipped. |
| Playwright Workbench UI inspection | Visible schedule and latest run state checked; temporary private snapshots removed; browser closed. |
| `git diff --check` | Failed on one unrelated pre-existing trailing-whitespace line in a GlassHive doc diff. |

## Stale, Skipped, Failed, Partial, Or Degraded Items

1. **High: memory-hardening LaunchAgent missed the local 03:00 scheduled run.** The machine was on
   AC, awake, and unconstrained; config/plist schedule is present; no run/log evidence exists for
   June 3. This is a clean missed execution, not a partial execution. Root cause remains open.
2. **Medium: the audit ran before the Workbench nightly due time.** The expected Workbench run is
   not late; it was due at 10:00Z. Today cannot be marked complete for that lane until a follow-up
   after 10:00Z verifies Scheduler -> GlassHive -> callback -> Workbench history.
3. **Medium: browser recall/vector-document proof remains unrun.** RAG health and stale clean
   hardener vector telemetry are supporting evidence only; the 401 metrics response means current
   vector/corpus counts were not proven.
4. **Medium: active user-level provider-reconnect rows remain.** Four active user-level schedules
   still report provider reconnect action. Their age needs classification before continuing to carry
   them as routine account-action follow-up.
5. **Medium: Primary AI Brain Setup copy is inconsistent.** Live status says configured; setup copy
   still says needs setup.
6. **Low: public diff hygiene has unrelated trailing whitespace.** `git diff --check` points at an
   existing GlassHive doc line not changed by this audit.

## Recommended Next Actions

1. Investigate the memory-hardening LaunchAgent scheduling path without forcing a model run:
   compare broader launchd unified logs, service load timing, macOS calendar-interval behavior,
   generated schedule reconciliation, and whether `install-schedule` should record/load-state
   observability.
2. Add a lightweight non-model schedule heartbeat or status field for the hardener so future audits
   can distinguish "not loaded", "loaded after due", "calendar skipped", "power skipped", and
   "wrapper started then skipped" without parsing private logs.
3. Run a short follow-up after `2026-06-03T10:00:00Z` to verify today's Workbench schedule completed
   and callback/outbox state stayed clean.
4. Keep browser recall/vector-document proof as a separate RAG QA pass; do not promote today's RAG
   `/health` check or stale vector telemetry to full recall signoff.
5. Determine whether the active provider-reconnect user-level rows are new, recurring, or stale
   across multiple cycles; escalate if they are not newly expected account-action rows.
6. Fix the Brain Setup Primary AI status mismatch in the status/readiness layer.

## ClaudeViv Review

`ClaudeViv` was not available as a separate binary, so local Claude Code CLI was used in
review-only mode with tools disabled and sanitized evidence. It returned JSON and made no changes.

Confirmed:

- The overall `PARTIAL` verdict is justified because Workbench was not due yet and RAG/browser
  recall proof remains incomplete.
- Memory hardening should be called a clean `FAIL`, not `FAIL/PARTIAL`, because preconditions were
  met and there was zero June 3 execution evidence.
- Workbench `NOT DUE / PARTIAL`, GlassHive callback `PASS`, continuity `PASS/PARTIAL`, and the eval
  pass counts are supported by the evidence.

Additional review concerns incorporated above:

- RAG evidence is only service-up plus stale clean vector telemetry; authenticated vector/corpus
  counts and browser recall are still missing.
- The separate scheduled exact-model eval lane is `N/A`, while the manually run suites themselves
  passed.
- Active user-level provider reconnect failures need age classification before they are treated as
  routine account-action follow-up.
