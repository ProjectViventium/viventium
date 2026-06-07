<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-06-01 Nightly Routines Health Review

Overall status: **PARTIAL / needs verification before repair**.

This was a read-only audit after the expected overnight window. The audit did not start model-backed
memory apply, transcript ingest, catch-up, vector rebuild, repair, background-agent work, runtime
stops, or owner-memory mutations.

## Scope

Docs and QA sources reviewed:

- `AGENTS.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/20_Memory_System.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/requirements_and_learnings/11_Scheduling_Cortex.md`
- `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`
- `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`
- `qa/README.md`
- `qa/memory-hardening/cases.md`
- `qa/meeting-transcript-memory/cases.md`
- `qa/memory-continuity/cases.md`
- `qa/prompt-workbench/cases.md`
- `qa/scheduling-cortex/cases.md`
- `qa/conversation-recall-rag/cases.md`

Private evidence stayed outside the public repo. This report uses aggregate counts, statuses,
timestamps, and redacted config presence only.

## Power And Safety Gate

| Check | Evidence | Status |
| --- | --- | --- |
| Current power source | Battery power, 45%, discharging at audit time | `PARTIAL` |
| Thermal state | No thermal/performance warning in the current sample | `PASS` for current sample only |
| Forced overrides | No `--ignore-power-gate`, `--ignore-idle-gate`, model apply, transcript catch-up, repair, or rebuild was run | `PASS` |

The current thermal sample does not prove the entire overnight window was unconstrained.

## Expected Vs Actual

| Routine | Expected overnight behavior | Actual evidence | Status |
| --- | --- | --- | --- |
| Memory hardening | LaunchAgent fires at the configured 03:00 schedule and performs bounded model-backed work only when power gates allow it. | LaunchAgent was installed, fired, and exited 0. The 2026-06-01 run recorded `on_battery_power`, so the latest model-backed run remains `20260531T100003Z` with `user_count=0`. Latest successful telemetry used Anthropic/Claude while the current generated config expects OpenAI/GPT-5.5, so no fresh telemetry proves current-provider parity. | `SKIPPED/PARTIAL` |
| Transcript ingest/catch-up | Transcript scan and vector lifecycle run only when memory hardening is allowed. | The 2026-06-01 hardener skipped before model-backed work. Prior transcript index still shows 47 files processed out of 47, but no fresh scan/vector lifecycle ran today. | `SKIPPED/PARTIAL` |
| Transcript summary/RAG artifacts | RAG service is reachable and transcript Mongo artifacts have matching vector presence before browser recall signoff. | RAG `/health` returned `UP`; RAG/vector containers were running. Mongo has 35 meeting-transcript file-context rows. Helper logs reported meeting-transcript Mongo artifacts missing from the vector store, and document-existence verification did not succeed. The JWT-secret injection path is not proven from generated env alone. | `PARTIAL/DEGRADED` |
| Scheduled Workbench deep-think routine | Built-in Workbench schedule dispatches through Scheduling Cortex -> GlassHive -> callback -> Workbench history. | Due `2026-06-01T10:00:00Z`, started `2026-06-01T10:20:45Z`, completed `2026-06-01T18:54:19Z`. Scheduler run, parent delivery ledger, GlassHive run, callback rows, and visible Workbench history agreed. The approximately 8h33m wall-clock duration needs an on-AC baseline before calling it a proven power/performance regression. | `PASS` delivery, `PARTIAL` duration baseline |
| Prompt benchmark / Workbench eval lane | Run if a scheduled nightly eval lane is documented. | No separate scheduled nightly exact-model eval lane was found in the reviewed docs/cases. Manual fixture evals passed. | `PASS` for documented lane, `FOLLOW-UP` to keep expectation explicit |
| Scheduler state | Scheduler health, delivery ledger, and due-run state agree; missed rows are visible. | Scheduler health returned `ok`. Last-24h scheduled prompt run delta had 1 completed and 0 failed. Active schedule summary still includes 9 active user-level rows last marked `missed/missed` with `misfire_grace_exceeded` from 2026-05-31. | `PARTIAL` |
| GlassHive callback outbox | No active callback retry backlog, and no fresh dead-letter delta for the latest run. | Callback outbox totals were 220 delivered and 2 dead-lettered historical rows; last-24h rows were delivered only. No pending, delivering, max-attempt, or oldest-pending backlog. Latest queued/started/completed callbacks delivered in one attempt. | `PASS` |
| Model/provider/fallback telemetry | Fresh nightly telemetry proves the configured provider/model path. | No fresh 2026-06-01 hardener telemetry because the job skipped on battery. The latest successful model-backed run does not match the current generated provider/model config. Helper logs also showed completion/fallback errors during other runtime activity. | `PARTIAL` |
| Status bar/manual ingest | Manual-ingest state is unchanged unless the user invoked it. | Helper/manual ingest logs showed no recent manual transcript ingest state change overnight. | `PASS/UNCHANGED` |
| Local web/search helpers | Enabled helper containers stay reachable through documented checks. | SearXNG health was OK and local Firecrawl containers were running, but the probed Firecrawl endpoint was not a valid health proof and those containers have no Docker healthcheck. | `PARTIAL/UNVERIFIED` for Firecrawl health |

## Evidence Checked

- LaunchAgent state, scheduled trigger, exit status, memory-hardening logs, and memory-hardening
  status summary.
- Current power and thermal state.
- Generated runtime config key presence for Workbench, GlassHive, memory hardening, transcript
  source, provider/model/effort, and RAG URL.
- Viventium status, active checkout alignment, and git drift summary.
- Scheduler health endpoint and sanitized SQLite task/run counts.
- GlassHive health, metrics, callback outbox counts, and latest scheduled run callback state.
- Prompt Workbench CLI status, API health, and real-browser Workbench view via Playwright.
- RAG health, Docker container state, SearXNG health, and Mongo aggregate counts.
- Helper logs for RAG document-existence verification and transcript vector artifact status.
- Continuity audit output, memory dedupe dry-run output, and focused release/eval test results.

No raw prompt text, memory values, transcript text, account identifiers, tokens, callback payloads,
private file names, screenshots, or browser snapshots were committed.

## Read-Only Commands Run

| Command | Result |
| --- | --- |
| `bin/viventium memory-harden status --json` | Latest model-backed run remained `20260531T100003Z`; latest 2026-06-01 scheduled attempt skipped on battery. |
| `bin/viventium status --json` | Core runtime surfaces reported running; status output was not machine JSON despite the flag. |
| `bin/viventium dev-runtime status --json` | Active/helper/live runtime checkouts aligned to the current checkout. |
| `curl` Scheduler `/health` | `ok`. |
| `curl` GlassHive `/health` and metrics summary | `ok`, no queued/active runs, no active callback backlog. |
| `curl` RAG `/health` | `UP`. |
| SQLite read-only scheduler queries | Last-24h scheduled prompt runs: 1 completed, 0 failed; current active user-level missed rows remain visible. |
| SQLite read-only GlassHive callback queries | Last-24h callback rows: delivered only; no fresh dead-letter delta. |
| Mongo aggregate read-only counts | 35 meeting-transcript file-context rows, 24 memory entries, no raw IDs copied. |
| Playwright CLI Workbench inspection | Workbench loaded, built-in schedule enabled, latest 2026-06-01 completed run visible; temporary snapshots were deleted. |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | `12 passed, 0 failed`. |
| `bin/viventium continuity-audit` | `status: ok`; local audit artifact stayed outside the public repo. |
| `bin/viventium memory-dedupe --dry-run --json` | Passed on retry after a transient CLI lock; 0 duplicate groups/docs and no writes. |
| Focused release suite with FastAPI/Uvicorn deps | `130 passed, 22 skipped`. |
| RAG/embeddings release tests | `5 passed`. |

The initial focused release-test attempt without FastAPI failed on a missing optional test
dependency, not a product assertion; it passed after adding the required test dependency.

## ClaudeViv Review

A review-only second opinion was run with a sanitized prompt and tools disabled. No dedicated
`ClaudeViv` binary was present, so the local Claude CLI was used as the ClaudeViv review path.

Confirmed by review:

- Overall `PARTIAL` is supported.
- Memory hardening and transcript work were skipped by design because of the battery gate.
- The Workbench scheduled prompt passed the functional delivery chain.
- Callback outbox health was clean for the latest run.
- Read-only and public-safety boundaries held.

Corrections incorporated:

- Workbench duration is now classified as `PARTIAL` needing an on-AC baseline, not as a proven
  degradation by itself.
- RAG/vector status is anchored on Mongo-vs-vector evidence and unverified JWT-secret injection,
  not on an unauthenticated 401 alone.
- Cumulative failed counts are not treated as overnight failures without last-24h deltas.
- Firecrawl health is marked unverified rather than proven by a wrong endpoint.

Unresolved risks from review:

- No fresh provider/model telemetry exists for the current generated hardener config.
- Transcript file-count delta versus the previous audit was not available.
- The nine active missed user-level schedules need owner/context classification.
- Helper installed-artifact parity was not proven during this read-only audit.
- Prompt benchmark/eval nightly expectation should stay explicit in docs/cases if it remains
  intentionally unscheduled.

## Follow-Up Actions

1. On the next AC-powered window, re-check `memory-harden status` after the scheduled run and
   compare the fresh provider/model/effort telemetry with generated runtime config.
2. Verify the RAG JWT-secret injection path and the Mongo-vs-vector transcript artifact mismatch
   read-only before any repair. If confirmed, fix the generated/shared auth path and rerun browser
   transcript recall QA afterward.
3. Establish an on-AC duration baseline for the built-in Workbench deep-think routine. Add a
   power/idle budget or explicit skip/defer policy only after the baseline confirms a regression.
4. Classify the 9 active `missed/missed` user-level schedules as expected sleep/battery misses,
   intentionally stale schedules, or scheduler defects.
5. Add or document a valid Firecrawl health probe for local status QA.
6. Keep the prompt-benchmark/eval nightly expectation explicit: either document no scheduled lane
   or add one if nightly evals become a product requirement.

## Case Status Updates

| Case | Status |
| --- | --- |
| `MEMHARD-001` | `SKIPPED/PARTIAL` |
| `MEMHARD-002` | `PASS` |
| `MEMHARD-003` | `PASS` for hardener gate, `PARTIAL` for adjacent Workbench power/duration baseline |
| `MTM-006` | `PARTIAL/DEGRADED` |
| `MEMCONT-001` | `PASS/PARTIAL` |
| `RAG-001` | `PARTIAL/DEGRADED` |
| `PW-029` / `PW-UC-009` | `PASS` delivery, `PARTIAL` duration baseline |
| `SCHED-002` / `SCHED-006` | `PASS` for latest built-in scheduled run |
| `SCHED-009` | `PASS` |
