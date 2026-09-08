# Scheduling Cortex QA Cases

## Case ID Convention

Use stable `SCHED-NNN` IDs for scheduling cortex cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `SCHED-001` | Create/update existing schedule | Browser/Telegram scheduling, Scheduling Cortex MCP | test_scheduling_mcp_supervision.py plus user-surface QA | PARTIAL 2026-08-08 — `SCHED-017` proves real one-time Telegram/Web create and delete; generic existing-schedule update, recurring change-only delivery, and restart behavior required by this broader case remain unrun. |
| `SCHED-002` | Trigger and delivery ledger | Scheduler trigger, delivery ledger, visible notification/chat | test_scheduling_mcp_supervision.py plus synthetic/live scheduled run | PASS 2026-08-09 ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md)); the natural 03:00 Workbench task completed through GlassHive/callback, and browser, joined integrity, and parent/child ledgers agreed. |
| `SCHED-003` | Auth/runtime failure copy | CLI/status, chat/tool failure copy | test_preflight.py or focused scheduler check | NOT RUN — cataloged 2026-05-17; execute when the owning feature changes. |
| `SCHED-004` | Runtime identity and port ownership | Launcher, `/health`, generated config, dev-env runtime | test_scheduling_mcp_supervision.py; test_stable_dev_runtime_workflows.py | PASS 2026-07-14; public status now also requires exact semantic status, service identity, and configured-ledger hash before showing Running ([report](../memory-continuity/reports/2026-07-14-memory-continuity-incident-repair.md)) |
| `SCHED-005` | GlassHive host overlap/backpressure | Scheduler due run, manual run, GlassHive host worker, callback ledger | Synthetic live scheduled run plus DB/API evidence | PARTIAL 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); source/runtime regressions now requeue retryable host-busy runs instead of terminal failure, but a live overlapping host-worker stress run is still outstanding |
| `SCHED-006` | Terminal callback updates parent task ledger | Scheduling Cortex callback, scheduled_prompt_runs, scheduled_tasks, Workbench status | Synthetic live scheduled run plus DB/API evidence | PASS 2026-07-10 ([callback repair](reports/2026-07-10-workbench-callback-repair.md)); fresh built-in Workbench manual run delivered queued/started/completed callbacks on first attempt and moved the child run plus parent task ledger to completed/success |
| `SCHED-007` | Stale GlassHive project cache recovery | Scheduler, GlassHive projects API, scheduled prompt metadata | test_scheduled_glasshive_prompts.py plus next live scheduled run | PASS 2026-05-27 ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); active-runtime stale task/definition project caches were replaced, the run completed, and Workbench visibly showed the completed run |
| `SCHED-008` | GlassHive host runtime dependency surfacing and safe recovery | Scheduler dispatch, GlassHive runtime preflight, generated env | test_scheduled_glasshive_prompts.py, test_config_compiler.py, test_preflight.py, live no-run host preflight | PASS 2026-05-30 ([RCA report](reports/2026-05-30-glasshive-host-runtime-dependency-rca.md), [nightly gaps follow-up](reports/2026-05-30-nightly-gaps-repair-followup.md)); structured `runtime_dependency_missing` is preserved, generated env emits the Codex binary path and GlassHive DB path, Codex.app discovery covers system/user app roots plus override, and safe scheduler recovery to docker is regression-covered |
| `SCHED-009` | Callback outbox bounded termination and health gate | GlassHive callback outbox, scheduler delivery ledger, metrics | GlassHive callback regressions plus nightly DB/API outbox-health probe | PARTIAL 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); queued/started/completed callbacks delivered on first attempt, active backlog and new dead letters were zero, while nine old dead letters and three old queued rows remain cleanup debt. |
| `SCHED-010` | Installer Scheduler readiness row, including the correctly seeded built-in task state. | Install/upgrade status, Scheduler health and ledger, Workbench run history | `test_install_summary.py`, `test_scheduled_glasshive_prompts.py`, `test_prompt_workbench.py` | PASS 2026-08-09 ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md)); the active built-in definition fired naturally through `glasshive_host`, completed, and advanced to the next 03:00 local occurrence. |
| `SCHED-011` | Orphaned user schedules stop retrying forever | Scheduler failure ledger, active flag, user ownership | `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/tests/test_scheduler.py` plus sanitized DB audit | PASS 2026-06-02; regression proves structured `scheduler/chat` `user_not_found` deactivates the task, preserves failed ledger evidence, and leaves transient/account-repair failures active; live cleanup retired three pre-fix active orphan rows |
| `SCHED-012` | Built-in nightly catch-up after a late scheduler tick | Scheduler misfire policy, Workbench task metadata, GlassHive callback, visible Workbench run history | `test_scheduled_glasshive_prompts.py::test_builtin_workbench_nightly_misfire_policy_catches_up_late_run` plus a future live delayed-tick proof | PARTIAL 2026-08-09: the automated catch-up regression passed and an on-time natural row completed, but the required late live catch-up was not exercised ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)). |
| `SCHED-013` | Scheduled agent runs use deterministic due-date context and do not drift day labels from prior same-conversation briefings | Scheduler dispatch, LibreChat scheduler gateway, Telegram/web delivery ledger | `test_dispatch.py`, `surfacePrompts.spec.js`, `test_config_compiler.py`, synthetic live scheduled run with Telegram/computer-use evidence | NOT RUN — cataloged 2026-06-15; execute with the scheduled-date-grounding fix. |
| `SCHED-014` | Built-in Workbench runs own explicit model/effort provenance and preserve structured failures. | Workbench, Scheduler, GlassHive host worker, callback ledgers | Workbench/Scheduler/GlassHive regressions plus live manual and automatic runs | PASS 2026-08-09 ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md)); the natural run completed with visible `xhigh -> xhigh` provenance while the Aug 8 structured failure remained visible as history. |
| `SCHED-015` | Recurring catch-up judges the latest eligible occurrence and manual startup uses canonical DB state. | Scheduler loop, delivery ledger, `/health` DB identity | `test_scheduler.py`, `test_bootstrap.py` | PARTIAL 2026-07-11: automated checks passed; the delayed live tick remains pending ([report](../memory-hardening/reports/2026-07-11-nightly-failure-prevention.md)) |
| `SCHED-016` | Scheduled Main inherits the complete persisted Agent Builder route and fallback without a scheduler-owned model override. | Compiler, Scheduling Cortex dispatch/instructions, scheduler route, agent initialization, Prompt Workbench, logs/DB | compiler/dispatch/Jest/Workbench regressions plus real scheduled run | PASS 2026-08-18; real Agent Builder/GlassHive run, browser refresh, Telegram delivery, ledger/log proof, and simulated fallback passed ([report](reports/2026-08-18-main-agent-builder-inheritance.md)) |
| `SCHED-017` | Main-Agent scheduling remains available when GlassHive is the conversation provider. | Telegram/web, Agent MCP declaration, GlassHive broker, Scheduling Cortex | compiler parity guard; projection/broker/route Jest; real Telegram and Test Account browser create/delete with DB/log evidence | PASS 2026-08-08; Telegram and browser each created one exact synthetic reminder and deleted it with zero residue; browser confirmation persisted after reload. Earlier attempts reproduced the stale inherited-signal failure. See [report](../glasshive-mcp-capability-broker/reports/2026-08-08-conversation-provider-scheduling-parity.md). |
| `SCHED-018` | Every scheduler executor and manual run uses one occurrence ledger. | Scheduler, `scheduled_prompt_runs`, Workbench | storage migration, lifecycle, GlassHive reuse, and manual-run regressions plus sanitized live rows | PARTIAL 2026-08-12: source regressions reproduced and repaired the persisted templated-refresh loss; all 145 Scheduling Cortex tests passed. The installed runtime, a fresh natural or synthetic occurrence, browser refresh, and the two historical duplicate-row pairs from the [nightly review](../memory-hardening/reports/2026-08-11-nightly-routines-health-review.md) remain unverified or unreconciled. |
| `SCHED-019` | Atomic leases make the scheduler nonblocking and exactly-once across processes. | Scheduler pool, SQLite/Redis-equivalent claim boundary, generation timeout, restart | two-engine race, saturation, expiry, crash/restart, timeout-versus-lease, long-run concurrency tests | PARTIAL 2026-08-29: 2026-08-11 lease automation passed, but the environment-configured generation timeout is not clamped below or coupled to the occurrence lease. |
| `SCHED-020` | `restart_daily` active windows produce the exact local 09:00–21:00 Toronto grid and latest-only recovery. | Scheduler recurrence, Workbench editor | DST/date-boundary/window/catch-up regressions plus projected daily count | PASS 2026-08-11: DST/window/grid regressions passed and Workbench showed 09:00–21:00, 45 minutes, 17 opportunities ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `SCHED-021` | Server-authored scheduler context is trusted and noninteractive; forged worker fields cannot gain origin, ownership, approval, revision, or delivery authority; current history uses typed metadata; trusted control/assistant `{NTA}` records stay hidden but auditable while literal user `{NTA}` stays visible. | Scheduler route, Main, Feelings, memory/recall, OAuth, visible history | authoritative-field forgery/overwrite matrix, current-typed versus legacy-untyped history, Reaction/memory counts, `{NTA}` visibility, cortex relevance, OAuth unavailable/confirmation tests | PARTIAL 2026-08-30: the 2026-08-11 typed-origin, exact-once Reaction, memory, basic forgery, cortex, and OAuth/confirmation subset passed; the full authoritative-field, typed/legacy history, and visibility matrix is NOT RUN ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `SCHED-022` | Registered scheduler prompts, compiled contract, Workbench source, and runtime text remain identical. | Prompt registry, compiled artifact, Python scheduler, Workbench | release contract equality tests plus browser source/effective-prompt inspection | PASS 2026-08-11: registry/shared/runtime equality passed and headed Workbench links opened the real editor ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `SCHED-023` | Same-Main continuity can act, plan, ask, communicate, or remain silent using all Feelings and existing authority. | Scheduled Main, tools, Feelings, memory/recall, LibreChat/Telegram, Workbench | exact-model mixed-state cases, capability-inventory comparison, silent/delivered live opportunities | FAIL 2026-08-25: the enabled 09:00–21:00 Toronto schedule retains its 45-minute cadence, but its five most recent natural opportunities failed with `completion_error`; joined cognitive integrity exposes `workbenchConsciousnessContinuity` as blocked. Earlier automated capability checks and historical silent opportunities do not prove the current installed path. |
| `SCHED-024` | A scheduled occurrence that launches one or more required durable missions remains `waiting_external` until the authoritative work—not merely one run—is terminal. | Scheduler occurrence, Core external-work binding, GlassHive multi-run callbacks, delivery ledger, Workbench | queued-follow-up callback reorder/replay, multiple required missions, restart, real Workbench refresh | NOT RUN — cataloged 2026-08-18 from the first retained dated repository reference; a completed source run and real multi-run Workbench persistence proof remain required. |
| `SCHED-025` | A signed late GlassHive completion repairs only a synthetic stale-run recovery failure and cannot overwrite genuine newer terminal evidence. | Scheduling Cortex callback, scheduled prompt/task ledgers, Workbench | signed route regression, lifecycle unit test, atomic compare-and-swap storage test, live restart/late-callback proof | PARTIAL 2026-08-13: automated checks prove a synthetic signed callback repairs `stale_run_reconciled`, preserves genuine terminal evidence, and loses safely to newer evidence. A real delayed callback after restart plus visible Workbench refresh remains required. |
| `SCHED-026` | Scheduled Main remains admissible with a large Active Work roster, retries durably after a rejected attempt, and gives the resulting conversation a public task title rather than an internal scheduler envelope. | Chrome, Scheduler, LibreChat, GlassHive conversation provider, SQLite ledger | scheduler route/context/title Jest, Scheduling Cortex dispatch, GlassHive validation-log regression, installed due-run and refresh proof | PASS 2026-08-18 ([report](reports/2026-08-18-scheduled-turn-context-budget-and-title.md)); the live installed-runtime proof showed the same failed one-time occurrence recover after activation, then a fresh one-time reminder delivered once with a task-derived title that persisted after refresh. |
| `SCHED-027` | `CC-002`: continuity is functional and never claims phenomenal consciousness. | continuity prompt, Workbench, visible delivery | source/rendered/live prompt scan plus exact-model visible-output QA | NOT RUN — cataloged 2026-08-30. |
| `SCHED-028` | `CC-003`: continuity reuses all nine Feelings and the existing Main, scheduler, memory, tools, history, job, and channel systems. | Scheduler, Main, Feelings, memory/recall, Workbench, Telegram, Voice | capability inventory and installed cross-surface journey | NOT RUN — cataloged 2026-08-30. |
| `SCHED-029` | `CC-005`: continuity adds none of the forbidden duplicate agents, stores, policies, dashboards, thresholds, or cancellation behavior. | source, schema, DB, runtime topology, Workbench | source/schema/DB inventory plus negative runtime checks | NOT RUN — cataloged 2026-08-30. |
| `SCHED-030` | `CC-006`: continuity opportunity and shared logical-turn behavior ship and activate together. | Scheduler, Web, Telegram, Voice, release artifacts | feature-flag/artifact parity and interrupted scheduled-turn journey | NOT RUN — cataloged 2026-08-30. |
| `SCHED-031` | `CC-013`: run disposition uses only the canonical seven states and maps empty Workbench-only output to `silent/audit_only`. | occurrence ledger and Workbench | enum/storage/API/UI contract tests | NOT RUN — cataloged 2026-08-30. |
| `SCHED-032` | `CC-016`: active-window behavior is opt-in and leaves legacy schedules unchanged. | scheduler recurrence, existing schedules, Workbench | before/after recurrence fixtures and visible editor QA | NOT RUN — cataloged 2026-08-30. |
| `SCHED-033` | `CC-026`: one editable and versioned schedule object owns timing and prompt selection without duplicating Main identity or tool policy. | Prompt Workbench, scheduler object, compiled prompt | edit/version/runtime lineage contract | NOT RUN — cataloged 2026-08-30. |
| `SCHED-034` | `CC-033`: one canonical scheduled result may fan out to Web and Telegram; voice delivery never starts an unsolicited call. | Web, Telegram, Voice, delivery ledger | cross-surface fanout and no-call assertion | NOT RUN — cataloged 2026-08-30. |
| `SCHED-035` | `CC-034`: public templates are inactive and private-preference-free; activation waits for every gate. | templates, canonical config, Workbench, release gate | template/privacy scan and gated activation fixture | NOT RUN — cataloged 2026-08-30. |
| `SCHED-036` | `CC-036`: empty continuity conversations stay archived, first visible delivery unarchives, and later silence does not rearchive. | Scheduler, conversation DB, Web/Telegram refresh | empty/delivered/silent state-transition journey | NOT RUN — cataloged 2026-08-30. |
| `SCHED-037` | `CC-037`: continuity creates no inner-monologue, digest, epilogue, or private-stream database. | source, schema, DB, runtime processes | forbidden-store inventory and migration scan | NOT RUN — cataloged 2026-08-30. |
| `SCHED-038` | `CC-052`: credential, provider, unsupported configuration, timeout, confirmation, healthy-empty, and rejected states remain distinct. | Scheduler, adapters, Workbench, user-visible errors | typed failure matrix plus recovery journey | NOT RUN — cataloged 2026-08-30. |
| `SCHED-039` | `CC-055`: disabled, edited, deleted, manual, Workbench-only, legacy, OAuth, confirmation, forgery, and durable-effect non-replay paths are explicit acceptance cases. | Scheduler, Workbench, OAuth, adapters, effect ledger | synthetic matrix and real-surface controls | NOT RUN — cataloged 2026-08-30. |
| `SCHED-040` | `CC-060`: activation follows the documented gate order; rollback disables only the continuity schedule and preserves shared fixes. | source, runtime, release artifacts, private activation control | ordered promotion/rollback checklist | NOT RUN — cataloged 2026-08-30. |
| `SCHED-041` | `CC-061`: ordinary turns receive no repetitive per-heartbeat appraisal narration. | Web, Telegram, Voice, occurrence/delivery ledgers | multi-heartbeat silence/usefulness journey | NOT RUN — cataloged 2026-08-30. |
| `SCHED-042` | `CC-062`: continuity rejects coercive engagement and Feeling-maximization objectives; silence remains valid. | prompt lineage, exact-model eval, visible delivery | positive/negative semantic cases plus no-delivery proof | NOT RUN — cataloged 2026-08-30. |
| `SCHED-043` | `CC-063`: Main has no evidence-delta keyword prefilter and proactive outreach stays bounded to an enabled owner-scoped schedule. | prompt/runtime source, schedule config, Web/Telegram | branch scan, disabled/enabled controls, and visible delivery QA | NOT RUN — cataloged 2026-08-30. |

## `SCHED-001` - Create/update existing schedule

- Scenario: Create or update a synthetic schedule from a real user surface and verify the visible
  confirmation against durable schedule state.
- Requirement: Create/update existing schedule.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Through the scheduling surface, create or update a synthetic reminder; verify visible confirmation, persisted schedule state, and no duplicate when updating existing briefing-style schedules.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_scheduling_mcp_supervision.py plus user-surface QA.
- Last run: PARTIAL 2026-08-08 — `SCHED-017` proves real one-time Telegram/Web create and delete. Generic
  existing-schedule update, recurring change-only delivery, and restart behavior remain NOT RUN.

## `SCHED-002` - Trigger and delivery ledger

- Scenario: Let a schedule become due and correlate its visible delivery or intentional silence
  with the durable delivery ledger.
- Requirement: Trigger and delivery ledger.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Run or simulate a due schedule; verify visible delivery or `{NTA}` suppression, ledger state, and final wording does not contradict tool state.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_scheduling_mcp_supervision.py.
- Last run: PASS 2026-08-09
  ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md));
  the natural 03:00 Workbench task completed through GlassHive/callback, and browser, joined
  integrity, and parent/child ledgers agreed.

## `SCHED-003` - Auth/runtime failure copy

- Scenario: Exercise scheduling with an unavailable or unauthenticated runtime and inspect the
  user-visible degraded-state wording.
- Requirement: Auth/runtime failure copy.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Disable or block the scheduler endpoint in a local-safe way; verify status/error copy identifies scheduler unavailability rather than claiming completion.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_preflight.py or focused scheduler check.
- Last run: NOT RUN — cataloged 2026-05-17; execute when the owning feature changes.

## `SCHED-004` - Runtime identity and port ownership

- Scenario: Start or probe two runtime contexts and verify the launcher accepts only the scheduler
  whose health identity matches the active runtime.
- Requirement: Scheduling Cortex is a per-runtime durable sidecar. The launcher must only accept a
  scheduler already listening on the configured port when `/health` proves it is attached to the
  same runtime DB/state; dev-env configs must use an isolated scheduler port and DB.
- Risk covered: A stale dev-env scheduler can satisfy local-prod health checks while due rows in
  the local-prod scheduler DB never advance.
- Preconditions: local runtime config can be compiled; focused scheduler test dependencies are
  available.
- Steps:
  1. Compile local-prod and dev-env runtime config and confirm the dev-env scheduler URL/port is
     isolated from local-prod and shared singleton ports.
  2. Start or probe a scheduler and confirm `/health` includes public-safe runtime identity hashes
     without raw local paths, secrets, or raw dev-env names.
  3. Run the launcher contract tests that prove mismatched, missing, or legacy health identity is a
     port-ownership conflict, not a success.
  4. Launch local prod and confirm the live scheduler health endpoint carries the expected identity
     shape.
- Expected result: local-prod scheduler ownership is identity-checked; dev-env scheduler ports are
  offset; missing/mismatched health identity fails loud and does not kill a foreign healthy runtime.
- Forbidden result: accepting `{"status":"ok"}` as sufficient runtime proof, killing another
  active runtime's scheduler by broad command pattern, or exposing raw local paths/secrets in
  public health, logs, or QA reports.
- Evidence to capture: sanitized health field names, compiled port summary, focused pytest
  results, launcher syntax result, live launch/status result, and public-safety scan.
- Automation: test_scheduling_mcp_supervision.py; test_stable_dev_runtime_workflows.py.
- Last run: PASS 2026-07-14; public status now also requires exact semantic status, service
  identity, and configured-ledger hash before showing Running
  ([report](../memory-continuity/reports/2026-07-14-memory-continuity-incident-repair.md)).

## `SCHED-005` - GlassHive host overlap/backpressure

- Scenario: Let a scheduled GlassHive run become due while host-worker capacity is occupied and
  verify durable retry or an honest degraded state.
- Requirement: Due scheduled Workbench/GlassHive runs must either execute durably or surface an
  honest retry/degraded state when host-worker capacity is already occupied.
- Risk covered: Multiple scheduled/manual GlassHive host runs can overlap, and the second run can
  fail even though the scheduler successfully reached GlassHive.
- Preconditions: local prod scheduler, Workbench, and GlassHive are running; synthetic
  public-safe prompts are used.
- Steps:
  1. Start a synthetic Workbench GlassHive manual run.
  2. While that host-native Codex worker is active, let a second synthetic one-time Workbench
     GlassHive schedule become due.
  3. Inspect Workbench API, DB run rows, callback summaries, and browser-visible run history.
- Expected result: the second run waits, coalesces, retries, or reports a durable blocked/retry
  state without losing the schedule outcome.
- Forbidden result: the second run is marked terminal failed solely because another host-native
  worker was active, with no retry/backpressure state.
- Evidence to capture: sanitized run statuses, callback event/status, task ledger status,
  Workbench visible row status, and no raw private prompt/path/token content.
- Automation: GlassHive runtime queue/backpressure regressions plus
  `tests/release/test_scheduled_glasshive_prompts.py`.
- Last run: PARTIAL 2026-05-27
  ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)).
  The runtime now requeues retryable `host_worker_busy` runs with backoff and a
  `run.waiting_on_capacity` callback instead of marking them terminal failed. Source/runtime
  regressions passed, but a live overlapping host-native worker proof is still outstanding.

## `SCHED-006` - Terminal callback updates parent task ledger

- Scenario: Complete or fail a scheduled GlassHive run and compare its signed terminal callback
  with the child run, parent task ledger, and visible Workbench state.
- Requirement: The parent scheduled task ledger must agree with terminal scheduled prompt callback
  state so user-facing status does not claim success when the run failed.
- Risk covered: `scheduled_prompt_runs.status=failed` while `scheduled_tasks.last_status=success`
  makes Workbench and scheduler diagnostics silently contradictory.
- Preconditions: a Workbench scheduled prompt run receives a terminal GlassHive callback.
- Steps:
  1. Trigger a synthetic Workbench GlassHive scheduled run that receives a terminal callback.
  2. Compare `scheduled_prompt_runs.status`, `scheduled_tasks.last_status`,
     `last_delivery_outcome`, and Workbench recent-run display.
  3. Repeat for `run.completed` and `run.failed`.
- Expected result: terminal callback status and parent task delivery ledger agree.
- Forbidden result: failed callback recorded only in `scheduled_prompt_runs` while the parent task
  remains `success`.
- Evidence to capture: sanitized DB/API status fields, callback event/status, and visible
  Workbench run row.
- Automation: `tests/release/test_scheduled_glasshive_prompts.py`.
- Last run: PASS 2026-07-10
  ([callback repair](reports/2026-07-10-workbench-callback-repair.md)); a fresh built-in Workbench
  manual run delivered queued, started, and completed callbacks on first attempt and moved the child
  run plus parent task ledger to completed/success.

## `SCHED-007` - Stale GlassHive project cache recovery

- Scenario: Dispatch a Workbench schedule whose cached GlassHive project is missing and verify
  replacement plus an honest visible run result.
- Requirement: Workbench scheduled prompts must not be permanently broken by a cached GlassHive
  project id that no longer exists in the GlassHive runtime.
- Risk covered: The Scheduler reuses a stale `glasshive_project_id`, GlassHive correctly returns
  404, and the nightly Workbench run fails forever even though Scheduler and GlassHive health checks
  are green.
- Preconditions: a Workbench scheduled prompt has task or definition metadata with a cached
  GlassHive project id; GlassHive is reachable.
- Steps:
  1. Simulate or create a scheduled prompt whose cached GlassHive project lookup returns 404.
  2. Dispatch the Workbench/GlassHive task.
  3. Verify Scheduling Cortex creates a replacement project, patches definition/task metadata, and
     assigns the run to the replacement project.
  4. On the active runtime, verify Workbench visible run history and Scheduler delivery ledger after
     a safe due/manual run.
- Expected result: a missing cached project is self-healed with a replacement project and the run is
  queued; non-404 GlassHive validation errors still fail loud.
- Forbidden result: blindly reusing stale cached project ids, silently converting non-404 runtime
  errors into new projects, or exposing raw project ids/private prompt text in public QA.
- Evidence to capture: sanitized project-cache validation result, source regression result,
  Scheduler ledger, Workbench visible run row, and GlassHive assignment summary.
- Automation: `tests/release/test_scheduled_glasshive_prompts.py`.
- Last run: PASS 2026-05-27
  ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); focused source
  regressions passed, then an active-runtime synthetic row with stale task and definition project
  caches replaced both caches and completed through GlassHive. Task cache, definition cache, and run
  ledger shared the replacement project hash.

## `SCHED-008` - GlassHive host runtime dependency surfacing and safe recovery

- Scenario: Dispatch a scheduled GlassHive run with a missing host dependency and verify the exact
  failure class or supported safe recovery path.
- Requirement: Workbench/GlassHive scheduled dispatch must preserve structured GlassHive runtime
  blockers, attempt configured safe recovery when the task has no host-specific constraint, and the
  generated runtime must expose host-worker dependencies exactly as the launched service sees them.
- Risk covered: A scheduler due run can fail before `/assign` with a generic HTTP 409 while the
  actual blocker is a missing host CLI in the LaunchAgent/helper service environment.
- Preconditions: GlassHive host workers are enabled and a synthetic public-safe Workbench
  dispatch/preflight can run without assigning a private prompt.
- Steps:
  1. Simulate `find-or-resume` returning structured `runtime_dependency_missing` and verify
     Scheduling Cortex preserves the failure class in `scheduled_prompt_runs`.
  2. Simulate host `runtime_dependency_missing` without a host workspace root and verify scheduler
     REST dispatch retries the same Workbench task through docker/sandbox execution before
     recording a terminal failure.
  3. Compile runtime config and verify host-worker env includes `WPR_CODEX_BIN`,
     `WPR_HOST_CODEX_CLI_AVAILABLE=true`, and local `WPR_DB_PATH`, including Codex.app system/user
     app-root discovery.
  4. Restart/probe GlassHive and run a synthetic `start_synchronously=false` `codex-cli` host
     preflight; verify a paused worker is accepted and no run row is created.
- Expected result: non-retryable runtime dependency failures fail loud with the real failure class;
  the fixed runtime preflight succeeds when a supported Codex binary path exists; safe
  sandbox/workstation recovery is attempted before terminal failure when host mode is unavailable
  and no host workspace root is required.
- Forbidden result: generic `HTTP 409: Conflict`, shell-only CLI availability, repo-local
  GlassHive DB fallback, asking first for global machine changes while safe recovery is available,
  or claiming success with a real assigned run that mutates private user work.
- Evidence to capture: sanitized generated env keys, structured failure class, App Support vs
  repo-local DB count comparison, safe recovery branch result, live no-run preflight summary, and
  focused test results.
- Automation: `tests/release/test_scheduled_glasshive_prompts.py`,
  `tests/release/test_config_compiler.py`, `tests/release/test_preflight.py`, and
  GlassHive runtime env tests.
- Last run: PASS 2026-05-30
  ([RCA report](reports/2026-05-30-glasshive-host-runtime-dependency-rca.md),
  [nightly gaps follow-up](reports/2026-05-30-nightly-gaps-repair-followup.md)); structured
  `runtime_dependency_missing` preservation, Codex app-root discovery, and scheduler REST recovery
  to docker are regression-covered; live proof used a synthetic paused worker and zero run rows.

## `SCHED-009` - Callback outbox bounded termination and health gate

- Scenario: Inspect callback-outbox health after a scheduled delivery and distinguish active,
  terminal, dead-letter, and historical residue states.
- Requirement: GlassHive callback delivery must be durable without retrying known-bad callback rows
  forever. Scheduler QA must prove both the latest delivery and the absence of stale delivery
  backlog.
- Risk covered: A fresh scheduled prompt can complete while old callback rows continue retrying a
  permanent HTTP failure every retry interval, hiding a delivery-substrate leak behind latest-run
  success.
- Preconditions: GlassHive runtime store is available with synthetic public-safe callback rows.
- Steps:
  1. Drive permanent and transient callback failures through the GlassHive callback outbox.
  2. Verify transient failures can still recover before the total budget.
  3. Verify permanent terminal failures and exhausted transient failures become `dead_lettered`
     with a retained audit row and `callback.dead_lettered` event.
  4. Verify stale `delivering` rows are reclaimed for replay.
  5. During nightly QA, query callback outbox health before and after the run: status counts,
     `dead_lettered` delta, oldest pending age, active-row max attempts, and stale `delivering`
     rows.
- Expected result: no callback row retries forever; terminal failures are visible and bounded;
  successful new callbacks still deliver; a fresh `dead_lettered` delta in an otherwise successful
  run fails the nightly health gate instead of being hidden by zero active backlog.
- Forbidden result: a `pending` callback row with growing attempts after permanent 4xx, invalid
  payload, missing URL, or exhausted transient retry budget; a stale `delivering` row that cannot
  re-enter replay; QA that only checks the latest successful callback while ignoring outbox health.
- Evidence to capture: sanitized callback status counts, `dead_lettered` before/after delta, active
  max attempts, oldest pending age, focused regression results, and newest scheduled prompt delivery
  status. Do not capture callback payload text, private prompt text, local paths, tokens, or user
  identifiers.
- Automation: GlassHive runtime callback regressions in `runtime_phase1/tests/test_api.py`; metrics
  outbox fields from `/v1/metrics/summary` or direct store query in read-only local QA.
- Last run: PARTIAL 2026-08-09
  ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md));
  queued, started, and completed callbacks delivered on first attempt, active backlog and new dead
  letters were zero, while nine old dead letters and three old queued rows remain cleanup debt.

## `SCHED-010` - Installer Scheduler Readiness Row

- Scenario: Inspect Scheduler readiness immediately after install or upgrade and correlate status
  output with health, durable task state, and Workbench history.
- Requirement: Easy Install Brain Readiness must expose Scheduler as a first-class installed
  surface, not an implicit Workbench detail.
- Risk covered: installer/status QA misses due schedules, delivery ledger, callback proof, or stale
  failed rows because Scheduler is not visible in the readiness model.
- Preconditions: generated runtime env and scheduler SQLite state are available with synthetic or
  sanitized rows.
- Steps:
  1. Compile an Easy Install (`install.experience: express`)-shaped config and confirm scheduler env keys are generated.
  2. Run install/status summary and confirm the Scheduler row shows service state plus sanitized
     ledger counts, latest status/outcome, and next run when available.
  3. Exercise degraded cases: endpoint down, DB missing, schema pending, and startup in progress.
  4. For release signoff, run the visible nightly chain: scheduled prompt -> filled placeholders ->
     GlassHive run -> callback -> scheduler ledger -> Workbench shows completed.
- Expected result: Scheduler status is readable without exposing prompt text, user IDs, callback
  payloads, or local paths; the latest visible Workbench result matches the ledger.
- Forbidden result: status only says Workbench is configured while Scheduler DB/callback health is
  uninspected, or public QA captures private schedule goals or callback payloads.
- Evidence to capture: sanitized env key presence, endpoint state, DB count/outcome/next-run
  summary, visible Workbench completion, and focused test results.
- Automation: `tests/release/test_install_summary.py`,
  `tests/release/test_scheduled_glasshive_prompts.py`, `tests/release/test_prompt_workbench.py`.
- Last run: PASS 2026-08-09
  ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md));
  the active built-in definition fired naturally through `glasshive_host`, completed, and advanced
  to the next 03:00 local occurrence.

## `SCHED-011` - Orphaned User Schedule Retirement

- Scenario: Let a recurring schedule run after its owning user is removed and verify only the
  orphaned task is retired with durable failure evidence.
- Requirement: A scheduled task whose owning user no longer exists must not remain active and fail
  every recurrence forever.
- Risk covered: Active orphan rows make status/QA look permanently degraded even though no user can
  receive or repair the schedule.
- Preconditions: local runtime or focused scheduler harness can simulate a
  `POST /api/viventium/scheduler/chat` `user_not_found` failure.
- Steps:
  1. Seed a recurring task for a synthetic user.
  2. Simulate a structured Scheduler -> LibreChat failure:
     `HTTP 404 (user_not_found): User not found`.
  3. Verify the task is inactive, `next_run_at` is cleared, and the delivery ledger records
     `last_delivery_outcome=failed` and `last_delivery_reason=orphaned_user_not_found`.
  4. Verify ordinary transient errors and account-reconnect failures still remain active for retry
     or user repair.
- Expected result: orphaned schedules are retired with ledger evidence and without deleting the
  row.
- Forbidden result: the scheduler retries a permanently ownerless task forever, deletes the row
  without evidence, or treats provider OAuth reconnect as an orphan.
- Evidence to capture: focused regression result, sanitized active-task status buckets, and
  truncated/hash-only owner identifiers when auditing a live DB.
- Automation:
  `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/tests/test_scheduler.py`.
- Last run: PASS 2026-06-02; focused scheduler test added and passed. Live DB audit found three
  pre-fix active orphaned user rows and four active provider-reconnect rows. The source fix retires
  future structured orphan failures while provider reconnect remains explicit account action; the
  three pre-fix orphan rows were then retired in local state with `orphaned_user_not_found` ledger
  evidence, reducing active scheduler rows from 11 to 8 without touching the built-in Workbench row.

## `SCHED-012` - Built-In Nightly Late Catch-Up

- Scenario: Process the built-in nightly Workbench reflection late but within its catch-up window
  and verify exactly one recovered occurrence.
- Requirement: the built-in nightly Workbench reflection must not be permanently lost when the local
  Scheduler loop first processes the due row after the normal misfire grace but still inside the
  documented catch-up window.
- Risk covered: Mac sleep, scheduler restart, or delayed local processing marks the built-in
  maintenance routine `misfire_grace_exceeded`, creating no child run, GlassHive run, callback, or
  visible Workbench result.
- Preconditions: the built-in `Subconscious Deep Thought` task is active, has structured
  `metadata.misfire_policy.mode=catch_up`, and GlassHive/Workbench are healthy.
- Steps:
  1. Run the synthetic regression that processes the built-in due row after the normal misfire grace
     and before the catch-up window expires.
  2. For future live QA, safely observe or deliberately simulate a late Scheduler tick on a
     public-safe built-in-shaped task.
  3. Verify child run, GlassHive run, callback, parent ledger, and visible Workbench run history all
     complete once.
  4. Verify `next_run_at` advances to the next period without accumulating missed days.
- Expected result: a single late but bounded built-in run is queued, records lateness, completes
  through GlassHive, and remains visible in Workbench.
- Forbidden result: missing the run without a child ledger, dispatching multiple catch-up runs for
  every missed period, relying on prompt/title/user matching, or hiding a failed GlassHive callback
  behind parent-task success.
- Evidence to capture: sanitized due/processed timestamps, late seconds/minutes, task metadata,
  child run status, parent delivery fields, GlassHive run/callback summary, visible Workbench row,
  and public-safety scan.
- Automation:
  `tests/release/test_scheduled_glasshive_prompts.py::test_builtin_workbench_nightly_misfire_policy_catches_up_late_run`.
- Last run: PARTIAL 2026-08-09: the automated catch-up regression passed and an on-time natural row
  completed, but the required late live catch-up was not exercised
  ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)).

## `SCHED-013` - Scheduled Run Date Grounding

- Scenario: Deliver a scheduled briefing after prior dated briefings exist and verify every visible
  day/date claim is grounded in the due occurrence and current evidence.
- Requirement: Scheduled `viventium_agent` generation receives deterministic due-date context and
  validates the opening generated date before Telegram/web fan-out.
- Risk covered: A recurring same-conversation morning briefing labels a due run as yesterday,
  tomorrow, or another stale date despite connected-account tools being available somewhere in the
  runtime.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Compose or trigger a synthetic daily scheduled run with `schedule.timezone`, `next_run_at`, and
     existing same-conversation history containing older dated briefings.
  2. Verify the scheduler prompt and LibreChat scheduler request carry `schedulerRunContext`,
     `clientTimestamp`, `scheduledDueAt`, the due local date, the ISO due-date tag, and the local/UTC
     calendar-day window.
  3. Verify generated delivery either has no opening date claim, has an opening date matching
     `scheduled_due_local_date`, or records `date_guard.status=corrected` before channel fan-out.
  4. For a Telegram-targeting task, verify the Telegram-visible text and Scheduler ledger agree with
     the corrected/passed date guard.
  5. Verify the guard does not rewrite first-line event dates that are not the leading opening date
     label.
- Expected result: visible delivery never labels the scheduled due run with the wrong day/date;
  calendar/email/task/current-day claims are grounded in verified tool/cortex evidence or omitted.
- Forbidden result: the model uses the next recurrence, server timezone fallback, prior briefing
  history, unverified Office availability, or an event-date false positive to assert or corrupt the
  day/date or calendar facts.
- Evidence to capture: sanitized prompt/run-context fields, focused test output, delivery ledger
  date-guard status, sanitized Telegram/computer-use observation, false-positive guard regression
  proof when applicable, and relevant log lines without raw
  private chat content.
- Automation:
  `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/tests/test_dispatch.py`;
  `viventium_v0_4/LibreChat/api/server/services/viventium/__tests__/surfacePrompts.spec.js`;
  `tests/release/test_config_compiler.py`.
- Last run: NOT RUN — cataloged 2026-06-15; execute with the scheduled-date-grounding fix.

## `SCHED-014` - Explicit Scheduled Model And Effort Provenance

- Scenario: Reconcile a legacy built-in Workbench row, run it through the configured provider, and
  inspect both successful provenance and a structured provider rejection.
- Requirement: Built-in Workbench runs own explicit model/effort provenance and preserve structured
  failures.
- Risk covered: migration or ambient developer configuration silently changes the model/effort, or
  a provider rejection is flattened into a generic failure.
- Preconditions: a synthetic legacy row, current Workbench/Scheduler/GlassHive runtime, and safe
  provider-rejection fixture are available.
- Steps:
  1. Seed or reconcile a legacy built-in row with missing model and invalid `max` effort.
  2. Confirm reconciliation preserves owner, prompt, active state, 03:00 schedule, timezone, and
     history while setting the supported host profile, model, and requested effort.
  3. Trigger a real safe run and correlate definition, bootstrap env, GlassHive command/evidence,
     signed callback, child row, parent ledger, and Workbench detail.
  4. Inject a synthetic provider rejection and confirm `provider_request_rejected` survives end to
     end.
- Expected result: ambient user config is ignored; requested and effective effort are both visible; any
  clamp has an explicit reason; failure class is not flattened.
- Forbidden result: `max` reaches the provider, model/effort is inferred from a developer shell, migration
  resets schedule/user state, or Workbench says generic failed when the provider rejected a request.
- Evidence to capture: reconciled row fields, configured and effective model/effort, GlassHive
  command/evidence, callback and ledger agreement, structured failure class, and Workbench detail
  after reload.
- Automation: Workbench, Scheduler, GlassHive, and callback provenance/failure regressions plus a
  live manual or automatic run.
- Last run: PASS 2026-08-09
  ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md));
  the natural run completed with visible `xhigh -> xhigh` provenance while the Aug 8 structured
  failure remained visible as history.

## `SCHED-015` - Latest-Occurrence Catch-Up And Canonical DB

- Scenario: Wake a stale recurring schedule inside and outside its catch-up window, then start the
  scheduler without an explicit DB-path override.
- Requirement: Recurring catch-up judges the latest eligible occurrence and manual startup uses
  canonical DB state.
- Risk covered: the oldest stale due date suppresses today's valid run, backlog occurrences replay,
  or startup silently selects a legacy database.
- Preconditions: a synthetic daily task, controllable scheduler clock, and isolated canonical and
  legacy DB fixtures are available.
- Steps:
  1. Persist a daily task ten days stale, then tick four hours after today's occurrence with a
     12-hour catch-up policy; confirm today dispatches once and its ledger names today's due
     timestamp.
  2. Tick thirteen hours after today's occurrence; confirm it skips today's occurrence and advances
     to tomorrow instead of reporting the oldest stale timestamp.
  3. Start path resolution without `SCHEDULING_DB_PATH`; confirm canonical App Support state is used
     and the legacy hidden-home database is never selected.
- Expected result: lateness, policy, and ledger all refer to the latest eligible occurrence; explicit DB
  path still wins and `/health` exposes only its hash.
- Forbidden result: oldest-stale lateness drops today's run, multiple backlog dispatches, legacy fallback
  DB, or raw local DB path in public health.
- Evidence to capture: stored due time, latest eligible occurrence, late seconds, next due time,
  dispatch count, selected DB identity hash, and sanitized health output.
- Automation: scheduler catch-up, bootstrap path-resolution, and health-identity regressions.
- Last run: PARTIAL 2026-07-11; automated checks passed, but the delayed live tick remains pending
  ([report](../memory-hardening/reports/2026-07-11-nightly-failure-prevention.md)).

## `SCHED-016` - Scheduled Main Agent Builder Inheritance

- Scenario: Run a synthetic scheduled Main turn and compare its route, provider, model, effort, and
  fallback with the persisted Agent Builder configuration.
- Requirement: Scheduled Main inherits the complete persisted Agent Builder route and fallback
  without a scheduler-owned model override.
- Risk covered: compiler, environment, or schedule metadata creates a second hidden Main policy and
  bypasses the user's current Agent Builder route or fallback.
- Preconditions: the current compiled runtime, persisted Main configuration, Prompt Workbench,
  browser/Telegram surfaces, and synthetic cleanup identifiers are available.
- Steps:
  1. Compile the supported runtime and verify no `runtime.scheduled_agent` schema/example field and
     no `VIVENTIUM_SCHEDULED_AGENT_*` output remain.
  2. Dispatch a synthetic scheduled `viventium_agent` run and verify Scheduler MCP sends no
     provider, model, effort, GlassHive, or fallback override; legacy override fields are ignored.
  3. Verify the authenticated scheduler route loads the persisted Main unchanged and agent
     initialization retains its Agent Builder provider/model/parameters, GlassHive options, and
     configured fallback.
  4. In Prompt Workbench, verify the route reads `Viventium Main (Agent Builder)`, model/effort are
     not configured on the schedule, and any observed model is historical run evidence.
  5. Start Prompt Workbench through its supported standalone command with no
     `SCHEDULER_LIBRECHAT_URL`; verify a manual Main run uses the compiled
     `VIVENTIUM_LIBRECHAT_ORIGIN` rather than the legacy `localhost:3080` fallback.
  6. Run one real synthetic scheduled control with Main configured to GlassHive, correlate visible
     browser/Telegram output with sanitized logs and DB, then exercise or safely simulate primary
     unavailability and prove the configured Agent Builder fallback is attempted.
  7. Remove the exact synthetic schedule, conversation, and messages and verify no matching QA rows
     remain.
- Expected result: future `viventium_agent` runs follow whatever Main is configured to use in Agent Builder;
  the current configured GlassHive primary and its fallback remain intact.
- Forbidden result: a compiler/env/schedule tuple replacing Main, deleting Agent Builder fallback, selecting
  policy from prompt/name/user text, or presenting old run provenance as current configuration.
- Evidence to capture: persisted Main configuration, compiled output, authenticated request and
  initialization trace, Workbench route display, visible browser/Telegram output, fallback result,
  ledger/log correlation, and zero-residue cleanup count.
- Automation: compiler, dispatch, route, initialization, and Workbench regressions plus one real
  scheduled control and safe fallback exercise.
- Last run: PASS 2026-08-18; real Agent Builder/GlassHive run, browser refresh, Telegram
  delivery, ledger/log proof, and simulated fallback passed
  ([report](reports/2026-08-18-main-agent-builder-inheritance.md)); synthetic local rows were removed.

## `SCHED-017` - Conversation-Provider Scheduling Parity

- Scenario: Ask naturally for a synthetic reminder while Main uses the GlassHive conversation
  provider, then inspect and delete the exact schedule through the same surface.
- Requirement: Main-Agent scheduling remains available when GlassHive is the conversation provider.
- Risk covered: a stale inherited request signal or incomplete capability projection makes the
  scheduler unavailable, produces fake success, or creates duplicate/residual rows.
- Preconditions: Main uses the GlassHive conversation provider; Telegram or authenticated browser,
  broker logs, Scheduling Cortex, and isolated synthetic data are available.
- Steps:
  1. Ask naturally through Telegram or browser for a synthetic one-time reminder. Do not mention
     broker internals or force a tool choice.
  2. Confirm the Agent-declared Scheduling Cortex server is included in a complete or truthfully
     partial structured provider projection and that any omission has a stable reason.
  3. Correlate the visible result with broker logs proving the provider call began with a live
     request-scoped signal and Scheduling Cortex received `CallTool`.
  4. Verify exactly one persisted row has the requested local time, timezone, and synthetic payload.
  5. Delete the exact synthetic schedule through the same surface, verify visible success and a
     second `CallTool`, then prove the database contains zero matching rows.
- Expected result: the model intelligently chooses scheduling from declared capability context; a healthy
  scheduler works through GlassHive with bounded replay protection and no hardcoded intent route.
- Forbidden result: matching prompt text/tool names/agent names in runtime code, declaring the scheduler
  unavailable because a completed outer signal was inherited, treating schema discovery as action
  success, duplicate schedules, fake confirmation, direct DB cleanup, or residual QA rows.
- Evidence to capture: visible create/delete replies and refresh, provider projection, request-signal
  and `CallTool` timestamps, persisted row fields, and zero-residue query.
- Automation: compiler parity, provider projection/broker/route regressions, and real Telegram and
  browser create/delete evidence.
- Last run: PASS 2026-08-08; Telegram and browser each created one exact synthetic reminder
  and deleted it with zero residue; browser confirmation persisted after reload. Earlier attempts
  reproduced the stale inherited-signal failure. See
  [report](../glasshive-mcp-capability-broker/reports/2026-08-08-conversation-provider-scheduling-parity.md).

## `SCHED-018` - One Occurrence Ledger Across Executors

- Scenario: Claim and execute one occurrence through scheduler and manual Workbench paths, then
  verify every executor reuses the same durable run row.
- Requirement: Every scheduler executor and manual run must reuse one keyed
  `scheduled_prompt_runs` occurrence ledger.
- Risk covered: template refresh or executor hand-off loses scheduler-private identity fields and
  creates a second, unkeyed run for the same occurrence.
- Preconditions: focused storage, lifecycle, GlassHive-reuse, and manual-run harnesses are
  available with synthetic rows; installed-runtime and browser proof are available for a full pass.
- Steps:
  1. Refresh a persisted templated task and verify all scheduler-private identity and trigger fields
     survive.
  2. Claim the occurrence through each supported executor and manual-run path.
  3. Verify every path reuses the claimed row and any missing identity fails closed before an
     unkeyed row is written.
  4. In live QA, run one occurrence, refresh Workbench, and reconcile the two historical duplicate
     row pairs identified by the linked nightly review.
- Expected result: one due occurrence has one durable run row across claim, execution, callback,
  manual visibility, and restart.
- Forbidden result: a templated refresh drops identity, an executor writes an unkeyed replacement,
  or source tests are presented as installed/browser proof.
- Evidence to capture: field-preservation regression, run-row identity/count, executor reuse,
  installed-runtime row, Workbench refresh, and historical-pair reconciliation.
- Automation: storage migration, lifecycle, GlassHive reuse, and manual-run regressions.
- Last run: PARTIAL 2026-08-12; all 145 Scheduling Cortex tests passed after reproducing and
  repairing the field-loss path. Installed-runtime, fresh-occurrence, browser-refresh, and
  historical duplicate reconciliation remain unverified ([nightly review](../memory-hardening/reports/2026-08-11-nightly-routines-health-review.md)).

## `SCHED-019` - Atomic Nonblocking Exactly-Once Leases

- Scenario: Race two scheduler engines for one occurrence, saturate the worker pool, then expire or
  crash the winning lease and verify exactly-once recovery.
- Requirement: Atomic leases must make scheduler work nonblocking and exactly once across
  processes, including expiry and restart. A configured generation timeout must remain below the
  occurrence lease or renew that exact lease safely.
- Risk covered: two scheduler engines execute one occurrence twice, or a saturated/crashed worker
  permanently strands claimed work; an unbounded stream-timeout override can also outlive the lease
  and permit another process to reclaim an occurrence while the first generation is still active.
- Preconditions: the two-engine race, saturation, expiry, crash/restart, and long-run concurrency
  harnesses are available with an isolated synthetic store.
- Steps:
  1. Race two engines for the same due occurrence and verify only one claim wins.
  2. Saturate the worker pool and verify the scheduler loop remains responsive.
  3. Exercise lease expiry, time-offset handling, and crash/restart reconciliation.
  4. Set the generation timeout at and above the occurrence lease and verify configuration is
     rejected, clamped, or coupled to safe lease renewal.
  5. Compare the authoritative ledger with its mirror after the run.
- Expected result: one process owns each valid lease, expired/crashed work recovers durably,
  generation cannot silently outlive its lease, and ledger mirrors remain consistent.
- Forbidden result: duplicate execution, blocking the scheduler loop on worker completion, or a
  lease that cannot recover after its owner dies.
- Evidence to capture: claim winners, lease timestamps, pool responsiveness, restart result, and
  mirror-integrity result.
- Automation: two-engine race, saturation, expiry, crash/restart, timeout-versus-lease, and long-run
  concurrency tests.
- Last run: PARTIAL 2026-08-29; the 2026-08-11 race, expiry/offset, crash reconciliation,
  worker-pool, and mirror-integrity gates passed, but current source accepts an unbounded integer
  `SCHEDULER_STREAM_TIMEOUT_S` override without clamping it below or coupling it to the occurrence
  lease ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)).

## `SCHED-020` - Toronto Active-Window Grid And Recovery

- Scenario: Configure a Toronto `restart_daily` active window across date and DST boundaries and
  verify its exact grid plus latest-only catch-up.
- Requirement: `restart_daily` active windows must produce the exact local 09:00-21:00 Toronto
  grid and recover only the latest eligible occurrence.
- Risk covered: DST or date-boundary math shifts the window, produces the wrong number of
  opportunities, or replays a backlog.
- Preconditions: recurrence tests can set Toronto dates around DST and Workbench can display a
  synthetic `restart_daily` schedule.
- Steps:
  1. Project the 09:00-21:00 window at 45-minute intervals on normal and DST boundary dates.
  2. Verify the projected grid contains 17 opportunities with exact local endpoints.
  3. Exercise delayed processing and confirm only the latest eligible occurrence is recovered.
  4. Open the Workbench editor and compare its displayed window and count with the recurrence
     result.
- Expected result: scheduler and Workbench agree on the Toronto grid, DST behavior, and latest-only
  recovery.
- Forbidden result: a UTC-derived local shift, an off-by-one opportunity, or replay of every missed
  interval.
- Evidence to capture: projected timestamps/count, DST/date-boundary regression results, catch-up
  identity, and Workbench window display.
- Automation: DST, date-boundary, active-window, catch-up, and projected-count regressions.
- Last run: PASS 2026-08-11; regressions passed and Workbench showed 09:00-21:00, 45 minutes, and 17
  opportunities ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)).

## `SCHED-021` - Trusted Noninteractive Scheduler Origin

- Scenario: Compare a server-authored scheduled Main turn, worker/client attempts to forge every
  trusted field, current typed history, imported legacy untyped history, and ordinary user chat
  across Reaction, memory, visibility, cortex, OAuth, and confirmation behavior.
- Requirement: `CC-007`, `CC-010`, and `CC-035` in
  `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: forged scheduler/worker origin, ownership, approval, turn revision, or delivery
  state gains authority; regex overrides current typed history; a scheduled turn writes
  Reaction/memory twice; trusted internal text leaks; literal user `{NTA}` is suppressed; or
  noninteractive execution disables useful cortex judgment.
- Preconditions: authoritative-field forgery/rejection-or-overwrite, current-typed and
  legacy-untyped history, Reaction/memory count, visibility/recall, cortex relevance, and OAuth
  unavailable/confirmation harnesses are available.
- Steps:
  1. Create the trusted context on the server, then submit worker/client variants that forge origin,
     ownership, approval, turn revision, and delivery state one field at a time and together.
  2. Verify each forged value is rejected or overwritten by the authoritative server value before
     policy runs, with the disposition retained for audit.
  3. Replay equivalent current typed and imported legacy untyped history. Verify typed fields alone
     govern current records and regex is used only when the legacy record has no typed equivalent.
  4. Compare Reaction and automatic-memory counts for scheduled and ordinary turns.
  5. Persist trusted scheduler control, assistant `{NTA}`, and literal user-authored `{NTA}` records;
     refresh UI, recall, automatic memory, and audit views.
     Let a useful scheduled answer overlap an ordinary user answer in the same conversation.
     Verify both answers appear without reload and after reload, then send a follow-up and inspect
     its parent. Switch ordinary and regenerated answer branches in Chat and Share; unselected
     ordinary branches stay hidden and an additive result never takes over the composer.
     Export selected/all branches as text, Markdown, and flat/recursive JSON. Reimport JSON and
     verify both answers, valid parent links, branch controls, and hidden control text.
  6. Exercise a scheduled request that needs an intelligent cortex.
  7. Exercise unavailable OAuth or confirmation-required behavior and verify it does not become an
     interactive hidden prompt.
- Expected result: only server-authored values receive trusted policy; every forged field is
  rejected or overwritten before policy; current typed history never uses regex; only legacy
  untyped history may use regex; Reaction/memory exclusion is exact; trusted control and assistant
  `{NTA}` stay hidden from UI, recall, and automatic memory but remain auditable; literal user
  `{NTA}` stays visible; relevant cortices remain available; unavailable authority is explicit.
- Forbidden result: trusting a worker/client marker, preserving a forged field, regex-reclassifying
  typed history, duplicate automatic writes, leaking trusted internal text, hiding literal user
  text, suppressing all cortices, or waiting indefinitely for interaction.
- Evidence to capture: authoritative values and rejection/overwrite receipts for every field,
  typed/legacy classification path, Reaction/memory counts, refreshed UI/recall/audit visibility,
  cortex decision, and OAuth/confirmation outcome.
- Automation: authoritative-field forgery matrix, typed/current and legacy/untyped history fixtures,
  Reaction/memory counts, `{NTA}` visibility/recall tests, cortex relevance, and OAuth
  unavailable/confirmation tests.
  Shared branch projection, Chat/Share selectors, composer ownership, and JSON structural-parent
  regressions support the overlapping-answer path; they do not replace visible delivery/reimport.
- Last run: PARTIAL 2026-08-30; the 2026-08-11 typed-origin, exact-once Reaction, memory, basic
  forgery, cortex, and OAuth/confirmation subset passed. The full five-field authority,
  typed-versus-legacy history, and trusted/literal visibility matrix is NOT RUN
  ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)).
  The overlapping-answer subset is PARTIAL on the current development candidate: stored answers
  display together in Chat/Share and export with valid parents; fresh live overlap and visible
  reimport remain open ([report](reports/2026-09-05-overlapping-result-visibility.md)).

## `SCHED-022` - Scheduler Prompt Contract Equality

- Scenario: Compare a scheduler prompt across registry, compiled artifact, Python runtime, and the
  Workbench source/effective-prompt views.
- Requirement: Registered scheduler prompts, compiled contract, Workbench source, and runtime text
  must remain identical.
- Risk covered: the scheduler runs stale or hidden prompt text that differs from the editable and
  versioned source shown to the user.
- Preconditions: prompt registry, compiled artifacts, Python scheduler source, and headed
  Workbench prompt links are available.
- Steps:
  1. Compare registry prompt text with the compiled artifact and Python runtime text.
  2. Open the linked Workbench source and effective prompt.
  3. Verify the editor points to the same owning prompt and does not hide an inline fallback.
- Expected result: all four representations are byte-consistent where equality is required and
  Workbench opens the real owning editor.
- Forbidden result: runtime-only prompt text, a stale compiled copy, or a Workbench link to a
  different/non-owning definition.
- Evidence to capture: equality-test output, artifact/source identities, and Workbench source and
  effective-prompt inspection.
- Automation: release contract equality tests plus browser source/effective-prompt inspection.
- Last run: PASS 2026-08-11; registry/shared/runtime equality passed and headed Workbench links
  opened the real editor ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)).

## `SCHED-023` - Same-Main Continuity Choice And Authority

- Scenario: Observe configured Same-Main continuity across mixed states and natural opportunities,
  including action, planning, questions, communication, silence, and structured failure.
- Requirement: Same-Main continuity may act, plan, ask, communicate, or remain silent using all
  Feelings and existing authority.
- Risk covered: the scheduled Main is reduced to a fixed action path, loses capability parity, or
  appears healthy from isolated tests while natural occurrences fail.
- Preconditions: exact configured model cases, capability inventory, enabled 09:00-21:00 Toronto
  schedule, and joined cognitive-integrity evidence are available.
- Steps:
  1. Run mixed-state exact-model cases that permit action, planning, asking, communication, and
     silence without forcing one outcome.
  2. Compare scheduled and ordinary Main capability inventories and Feelings access.
  3. Observe natural silent and delivered opportunities through the installed path.
  4. Correlate every failure with child/parent ledger and joined cognitive-integrity status.
- Expected result: the model retains full relevant authority and each natural opportunity records
  an honest delivered, silent, waiting, or structured failure state.
- Forbidden result: hardcoded intent routing, a reduced scheduled capability inventory, or an
  automated subset used to override current installed failures.
- Evidence to capture: sanitized mixed-state outputs, capability comparison, natural-opportunity
  ledgers, visible delivery/silence, and joined integrity.
- Automation: exact-model mixed-state cases and capability-inventory comparison; live silent and
  delivered opportunities remain a separate gate.
- Last run: FAIL 2026-08-25; five most recent natural opportunities failed with
  `completion_error`, and joined integrity marks `workbenchConsciousnessContinuity` blocked.
  Earlier automated checks and historical silent opportunities do not prove the current installed
  path.

## `SCHED-024` - Durable Mission Completion Binding

- Scenario: Launch multiple required durable missions from one scheduled occurrence, replay their
  callbacks around a restart, and verify terminal state only after all required work finishes.
- Requirement: A scheduled occurrence that launches one or more required durable missions must
  remain `waiting_external` until all authoritative work, not merely one run, is terminal.
- Risk covered: the scheduler marks an occurrence complete after the first callback while required
  follow-up or parallel missions are still active, or loses bindings after restart.
- Preconditions: synthetic queued-follow-up and multiple-required-mission fixtures, signed callback
  replay/reorder harnesses, restart support, and Workbench are available.
- Steps:
  1. Bind one occurrence to more than one required durable mission.
  2. Deliver queued, follow-up, and terminal callbacks out of order and replay duplicates.
  3. Restart while at least one required mission remains active.
  4. Refresh Workbench and verify the occurrence becomes terminal only after every authoritative
     binding is terminal.
- Expected result: the occurrence stays `waiting_external` while required work remains and reaches
  one honest terminal result after complete authoritative evidence.
- Forbidden result: first-run-wins completion, duplicate callback mutation, dropping bindings on
  restart, or Workbench showing terminal before the ledger does.
- Evidence to capture: occurrence-to-mission bindings, callback order/replay results, restart state,
  terminal transition, and Workbench refresh.
- Automation: queued-follow-up reorder/replay, multiple required missions, and restart regressions;
  real Workbench persistence remains required.
- Last run: NOT RUN — cataloged 2026-08-18 from the first retained dated repository reference; no
  completed source run or real multi-run Workbench proof is recorded.

## `SCHED-025` - Late GlassHive Completion Reconciliation

- Scenario: Deliver a valid signed completion after restart for a run marked with the synthetic
  stale-recovery failure, then compare genuine and newer terminal controls.
- Requirement: Startup recovery may mark an abandoned scheduled GlassHive run failed, but a later
  valid signed `run.completed` callback from that exact run must replace only the synthetic
  `stale_run_reconciled` placeholder and reconcile the child and parent ledgers.
- Risk covered: a long or temporarily disconnected GlassHive run completes after Scheduling Cortex
  has crossed its recovery horizon; the endpoint returns HTTP accepted while silently discarding
  the authoritative result and leaving Workbench permanently failed.
- Preconditions: signed callback fixtures, child and parent ledger storage, restart/lifecycle
  harnesses, genuine-failure and newer-terminal controls, and Workbench are available.
- Steps:
  1. Persist a scheduled GlassHive run as `failed/stale_run_reconciled` and submit its correctly
     signed late completion callback.
  2. Verify the run becomes completed/delivered, callback summary persists, and parent-ledger
     reconciliation is invoked only after the atomic lifecycle update wins.
  3. Repeat with a genuine provider failure and with a simulated newer-terminal race.
- Expected result: only the synthetic recovery placeholder is repairable; genuine completion,
  cancellation, or provider-failure evidence remains terminal-wins.
- Forbidden result: HTTP 200 with `callback_persisted=false` for the recoverable late completion,
  or any late callback overwriting newer genuine terminal evidence.
- Evidence to capture: signed endpoint result, sanitized child/parent status fields, Workbench row
  after refresh, and duplicate/out-of-order callback behavior.
- Automation: `tests/test_bootstrap.py`, `tests/test_server_lifecycle.py`, and
  `tests/test_storage.py`.
- Last run: PARTIAL 2026-08-13; focused endpoint/lifecycle/storage regressions passed.
  Installed-runtime restart timing and browser-visible Workbench persistence are not yet proven.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Scheduling Cortex. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-001` | On Browser/Telegram scheduling, Scheduling Cortex MCP, verify that create/update existing schedule. | owning requirement for `SCHED-001` / `SCHED-001` | Browser/Telegram scheduling, Scheduling Cortex MCP | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-001. | The visible result for SCHED-001 matches the documented requirement. | PARTIAL 2026-08-08 — `SCHED-017` proves real one-time Telegram/Web create and delete; generic existing-schedule update, recurring change-only delivery, and restart behavior remain NOT RUN. |
| `SCHED-UC-002` | On Scheduler trigger, delivery ledger, visible notification/chat, try trigger and delivery ledger with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `SCHED-002` / `SCHED-002` | Scheduler trigger, delivery ledger, visible notification/chat | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-002. | The user sees an honest setup, retry, or degraded-state result for SCHED-002; no fake success is accepted. | PASS 2026-08-09 ([continuity report](../memory-continuity/reports/2026-08-09-universal-cognitive-continuity-parity.md)); the natural 03:00 Workbench task completed through GlassHive/callback, and browser, joined integrity, and parent/child ledgers agreed. |
| `SCHED-UC-003` | After auth/runtime failure copy, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `SCHED-003` / `SCHED-003` | CLI/status, chat/tool failure copy | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-003. | SCHED-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT RUN — cataloged 2026-05-17; execute when the owning feature changes. |
| `SCHED-UC-004` | Start local prod while another runtime has or had a scheduler on the default port. | owning requirement for `SCHED-004` / `SCHED-004` | Launcher, generated config, `/health`, status | Source, owning requirement doc, focused tests, compiled config, live health, and runtime status evidence that apply to SCHED-004. | The launcher accepts only the scheduler with matching public-safe runtime identity and fails loud on foreign/legacy ownership. | PASS 2026-07-14; public status requires exact semantic status, service identity, and configured-ledger hash before showing Running ([report](../memory-continuity/reports/2026-07-14-memory-continuity-incident-repair.md)). |
| `SCHED-UC-005` | Let a Workbench/GlassHive schedule become due while another host-native Codex worker is active. | owning requirement for `SCHED-005` / `SCHED-005` | Scheduler, GlassHive host worker, Workbench run history | Sanitized callback, run-row, parent task ledger, and browser-visible run history evidence. | The user sees a queued/retry/degraded state rather than a terminal failed run with no retry. | PARTIAL 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); source/runtime regressions passed, live overlap stress remains |
| `SCHED-UC-006` | Compare terminal GlassHive callback status with the parent task ledger after a run completes or fails. | owning requirement for `SCHED-006` / `SCHED-006` | Callback endpoint, DB, Workbench | Sanitized scheduled_prompt_runs and scheduled_tasks fields plus browser-visible run row. | Parent task status and delivery fields agree with the terminal run status. | PASS 2026-07-10 ([callback repair](reports/2026-07-10-workbench-callback-repair.md)); a fresh built-in Workbench manual run delivered queued, started, and completed callbacks on first attempt and moved the child run plus parent task ledger to completed/success. |
| `SCHED-UC-007` | Let a Workbench scheduled prompt with a stale GlassHive project cache run. | owning requirement for `SCHED-007` / `SCHED-007` | Scheduler, GlassHive projects API, Workbench run history | Sanitized project-cache validation, task/definition metadata summary, Scheduler ledger, and visible Workbench run row. | Scheduler replaces the missing cached project and the user sees an honest queued/completed/failed result tied to the new project. | PASS 2026-05-27 ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); source regression and active-runtime stale-cache manual proof both passed |
| `SCHED-UC-008` | Let a Workbench/GlassHive scheduled dispatch encounter a host runtime dependency blocker before `/assign`. | owning requirement for `SCHED-008` / `SCHED-008` | Scheduler, generated env, GlassHive host preflight | Sanitized structured error class, generated env key summary, safe recovery branch result, and no-run host preflight DB proof. | The user/admin sees the real dependency class, the fixed runtime accepts host `codex-cli` without creating a run, or the same task safely recovers to sandbox/workstation mode before terminal failure. | PASS 2026-05-30 ([RCA report](reports/2026-05-30-glasshive-host-runtime-dependency-rca.md), [nightly gaps follow-up](reports/2026-05-30-nightly-gaps-repair-followup.md)); structured error preservation, safe recovery regression, and live no-run host preflight passed |
| `SCHED-UC-009` | Inspect callback outbox health after scheduled Workbench/GlassHive delivery. | owning requirement for `SCHED-009` / `SCHED-009` | GlassHive metrics, callback outbox DB, Workbench run history | Sanitized callback status counts, before/after dead-letter delta, oldest pending age, active max attempts, terminal dead-letter count, and latest scheduled run ledger. | Latest delivery can succeed only if the delivery substrate also has no unexplained stale/high-attempt pending callback rows and no fresh dead-letter delta. | PARTIAL 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); completion callbacks delivered once, active backlog and new dead letters were zero, but old queued/dead-letter rows remain cleanup watch. |
| `SCHED-UC-010` | Inspect Scheduler readiness immediately after Easy Install or upgrade. | `39_Installer_and_Config_Compiler.md` / `SCHED-010`, `INST-004` | `bin/viventium status`, scheduler health endpoint, scheduler SQLite ledger, Workbench run history | Sanitized endpoint result, DB count/status/outcome/next-run summary, generated env keys, focused tests. | Scheduler is visible as installed/configured/running/degraded with a concrete next action and no private schedule data in public output. | PASS 2026-08-09; joined integrity and refreshed Workbench both show the natural due run completed, the active definition healthy, and the next occurrence advanced. |
| `SCHED-UC-011` | Let a recurring task fail because its owner user no longer exists. | `11_Scheduling_Cortex.md` / `SCHED-011` | Scheduler failure ledger, active flag, sanitized DB audit | Focused scheduler regression plus hash/truncated live DB evidence. | The orphaned task becomes inactive with `orphaned_user_not_found` ledger evidence; non-orphan auth/provider failures are not hidden. | PASS 2026-06-02; focused regression passed, live audit classified orphan rows separately from provider reconnect rows, and three pre-fix orphan rows were retired from active state |
| `SCHED-UC-012` | Let the built-in nightly Workbench reflection be processed late but inside the catch-up window. | `11_Scheduling_Cortex.md` / `SCHED-012`, `PW-029` | Scheduler loop, GlassHive, Workbench run history | Sanitized late timing, child/parent ledger fields, GlassHive callback, visible Workbench row. | The late built-in routine runs once, records lateness, advances to the next period, and Workbench shows completed. | PARTIAL 2026-08-09: the automated catch-up path passed; the natural occurrence was on time and therefore did not prove this late-catch-up use case ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)). |
| `SCHED-UC-013` | Receive a scheduled morning-style briefing through Telegram/web after prior same-conversation dated briefings exist. | `11_Scheduling_Cortex.md` / `SCHED-013` | Scheduler, Telegram/computer-use, delivery ledger, Mongo/tool-call state | Sanitized scheduled run context, opening date label, date-guard status, tool/cortex evidence count/classification, logs, and persisted message summary. | The visible briefing is anchored to the due local date and does not assert unverified calendar/email/task facts. | NOT RUN — cataloged 2026-06-15; execute with SCHED-013 implementation QA. |
| `SCHED-UC-014` | Open the built-in 03:00 Workbench schedule, trigger it safely, and inspect the terminal run. | `11_Scheduling_Cortex.md` / `SCHED-014`, `PW-037` | real Prompt Workbench, Scheduler, GlassHive | definition/bootstrap/effective tuple, callbacks, child/parent ledger, visible detail | Workbench shows configured model and requested to effective effort; terminal status preserves the real failure class or completion. | PASS 2026-08-09; refreshed Workbench showed the natural scheduled run completed with `xhigh -> xhigh`, current evidence/artifact validation passed, and prior failures remained visible. |
| `SCHED-UC-015` | Wake the host after several missed recurring periods while today's run is still in its catch-up window. | `11_Scheduling_Cortex.md` / `SCHED-015` | Scheduler, Workbench run history, delivery ledger | stored old due time, latest occurrence, late seconds, next due, DB identity hash | Today's occurrence runs once or is skipped by today's lateness, then advances correctly without using a legacy DB. | PARTIAL 2026-07-11: automated checks passed, but the delayed live tick remains pending ([report](../memory-hardening/reports/2026-07-11-nightly-failure-prevention.md)) |
| `SCHED-UC-016` | Let a user-created Viventium-agent automation run, compare its route and fallback with the current Main Agent Builder configuration, then clean the synthetic run. | `11_Scheduling_Cortex.md` / `SCHED-016` | real Scheduler/LibreChat route, logs, Mongo, browser when visible | persisted Main configuration, authenticated request metadata, initialization trace, exact response, fallback state, cleanup count | The scheduled turn uses whatever Main is configured to use in Agent Builder—including the current GlassHive primary and configured fallback—ordinary chat is not globally rewritten, simulated fallback is not presented as a live fault, and exact QA residue is zero. | PASS 2026-08-18; real Browser and Telegram runs inherited the persisted GlassHive Main, the configured fallback was safely simulated, and exact synthetic residue was removed. See the [dated report](reports/2026-08-18-main-agent-builder-inheritance.md). |
| `SCHED-UC-017` | Ask Viventium in Telegram and the Test Account browser for a one-time synthetic reminder, inspect it, reload browser, and delete it. | `11_Scheduling_Cortex.md` / `SCHED-017`, `GH-MCP-BROKER-021` | Telegram Desktop, authenticated LibreChat, GlassHive conversation provider, broker, Scheduling Cortex | Visible create/delete replies, browser refresh, provider projection and signal logs, `CallTool` timestamps, persisted row then zero-residue query | The model chooses the scheduler from declared capabilities, confirms only after tool success, creates exactly one correct reminder per isolated account, preserves the browser result after reload, deletes only that reminder, and leaves no residue. | PASS 2026-08-08 on both native surfaces; see [report](../glasshive-mcp-capability-broker/reports/2026-08-08-conversation-provider-scheduling-parity.md). |
| `SCHED-UC-018` | Trigger one synthetic occurrence through the scheduler and manual Workbench paths, then refresh Workbench. | `11_Scheduling_Cortex.md` / `SCHED-018` | Scheduler, `scheduled_prompt_runs`, Workbench | Identity-field preservation, executor reuse, run-row count, installed row, browser refresh, and duplicate-pair reconciliation. | Every path shows one durable keyed occurrence row; no unkeyed duplicate appears. | PARTIAL 2026-08-12; 145 source tests passed, while installed-runtime, fresh-occurrence, browser-refresh, and historical duplicate reconciliation remain unverified ([nightly review](../memory-hardening/reports/2026-08-11-nightly-routines-health-review.md)). |
| `SCHED-UC-019` | Run two scheduler engines against one due occurrence, set the generation timeout at or above the occurrence lease, then crash and restart the lease owner. | `11_Scheduling_Cortex.md` / `SCHED-019` | Scheduler pool, claim store, timeout configuration, restart | Claim winner, lease expiry/offset, timeout-versus-lease result, pool responsiveness, restart recovery, and mirror integrity. | Exactly one engine executes the occurrence; generation cannot silently outlive its lease; expired or crashed work recovers without blocking the loop. | PARTIAL 2026-08-29; prior lease automation passed, but current source accepts an unbounded `SCHEDULER_STREAM_TIMEOUT_S` override without a timeout-versus-lease guard. |
| `SCHED-UC-020` | Configure a 09:00-21:00 Toronto `restart_daily` window at 45-minute intervals and inspect it in Workbench. | `11_Scheduling_Cortex.md` / `SCHED-020` | Scheduler recurrence, Workbench editor | DST/date-boundary grid, projected count, latest eligible occurrence, and visible editor values. | Scheduler and Workbench show the exact 17-opportunity Toronto grid and recover only the latest eligible occurrence. | PASS 2026-08-11; automated DST/window/grid checks passed and Workbench showed 09:00-21:00, 45 minutes, and 17 opportunities ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `SCHED-UC-021` | Let a server-authored scheduled Main turn need a cortex or unavailable OAuth action; forge worker origin, ownership, approval, turn revision, and delivery state; then compare current typed, legacy untyped, and ordinary chat history. | `CC-007`, `CC-010` / `SCHED-021` | Scheduler route, Main, Feelings, memory/recall, OAuth | Server values, per-field rejection/overwrite receipts, typed-versus-legacy classification path, Reaction/memory counts, cortex relevance, and OAuth/confirmation outcome. | Forged fields are rejected or overwritten before policy; current history uses typed metadata and regex only legacy untyped history; scheduler origin remains noninteractive and excludes exactly the intended Reaction/automatic-memory effects without disabling relevant cortices or hiding unavailable authority. | PARTIAL 2026-08-30; the 2026-08-11 typed-origin, memory, basic forgery, cortex, and OAuth/confirmation subset passed, but the full field and history matrix is NOT RUN ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `SCHED-UC-022` | Open a scheduler prompt in Workbench and compare its source and effective text with the registry, compiled artifact, and runtime. | `11_Scheduling_Cortex.md` / `SCHED-022` | Prompt registry, compiled artifact, Python scheduler, Workbench | Equality-test output, source/artifact identities, and headed source/effective-prompt inspection. | Every owning representation agrees, and Workbench opens the real editor with no hidden runtime fallback. | PASS 2026-08-11; equality tests passed and headed Workbench links opened the real editor ([report](reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `SCHED-UC-023` | Observe enabled Same-Main continuity opportunities and allow Main to act, plan, ask, communicate, or remain silent. | `11_Scheduling_Cortex.md` / `SCHED-023` | Scheduled Main, tools, Feelings, memory/recall, LibreChat/Telegram, Workbench | Exact-model mixed-state results, capability comparison, natural ledgers, visible delivery/silence, and joined integrity. | Main keeps full relevant authority and each opportunity records an honest delivered, silent, waiting, or structured failure state. | FAIL 2026-08-25; five most recent natural opportunities failed with `completion_error`, and joined integrity marks the path blocked. Earlier automated checks do not prove the current installed path. |
| `SCHED-UC-024` | Start a scheduled occurrence that launches multiple required durable missions, restart mid-flight, and refresh Workbench. | `11_Scheduling_Cortex.md` / `SCHED-024` | Scheduler occurrence, Core external-work binding, GlassHive callbacks, Workbench | Mission bindings, reordered/replayed callbacks, restart state, terminal transition, and browser refresh. | The occurrence remains `waiting_external` until every required authoritative mission is terminal. | NOT RUN — cataloged 2026-08-18 from the first retained dated repository reference; no completed source run or real multi-run Workbench persistence proof is recorded. |
| `SCHED-UC-025` | Deliver a valid signed late completion after restart for a run marked `failed/stale_run_reconciled`, then refresh Workbench. | `11_Scheduling_Cortex.md` / `SCHED-025` | Scheduling Cortex callback, child/parent ledgers, Workbench | Signed endpoint result, atomic lifecycle result, genuine-failure control, newer-terminal race, and visible refresh. | Only the synthetic stale-recovery placeholder is repaired; genuine or newer terminal evidence remains unchanged. | PARTIAL 2026-08-13; focused source tests passed, but a real delayed callback after restart and visible Workbench refresh remain required. |
| `SCHED-UC-026` | Run a synthetic reminder with a large Active Work roster, let its rejected occurrence retry, and inspect the refreshed conversation title. | `11_Scheduling_Cortex.md` / `SCHED-026` | Chrome, Scheduler, LibreChat, GlassHive provider, SQLite ledger | Context validation class, durable task/run rows, provider result, visible delivery/title, refresh, and cleanup. | The same occurrence retries once without duplicate delivery, and the persisted title is public and task-derived. | PASS 2026-08-18; installed due-run, retry, delivery, and refresh proof passed ([report](reports/2026-08-18-scheduled-turn-context-budget-and-title.md)). |
| `SCHED-UC-027` | Ask a continuity result what it is and inspect its prompt lineage and visible wording. | `CC-002` / `SCHED-027` | Prompt Workbench and one visible scheduled result | source/rendered/live prompt, model output, persisted message, and privacy scan | The system describes functional continuity and never claims phenomenal consciousness. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-028` | Run one synthetic continuity opportunity that needs Feelings, memory, a tool, history, and one configured delivery surface. | `CC-003` / `SCHED-028` | Scheduler, Main, Workbench, and configured surface | nine-band snapshot, capability inventory, recall/tool receipts, job state, and delivery ledger | The existing Main and existing systems handle the run; every required existing capability is available without a duplicate subsystem. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-029` | Enable one synthetic continuity schedule and inspect source, schemas, databases, processes, and controls before and after its run. | `CC-005` / `SCHED-029` | repository, runtime topology, DB schema, and Workbench | forbidden-component inventory, migrations, process list, config diff, and run result | No forbidden agent, store, policy, dashboard, threshold, cap, cooldown, temporary thread, merge, or implicit cancellation appears. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-030` | Interrupt one scheduled Main answer with a newer stable segment on each enabled text surface after installing the candidate from its artifacts. | `CC-006` / `SCHED-030` | Scheduler, Web, Telegram, Voice adapter contract, and installed artifacts | feature flags, built identities, logical revisions, persistence, and delivery acknowledgements | Continuity and logical-turn behavior are present together; no surface runs only one half of the contract. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-031` | Produce one run for each terminal/nonterminal disposition and one empty Workbench-only run, then reload history. | `CC-013` / `SCHED-031` | Scheduler ledger and Prompt Workbench | stored enum, audit-only subtype, API projection, visible history, and refresh | Only the seven canonical dispositions appear; empty audit-only work is `silent/audit_only`, not a delivery failure. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-032` | Upgrade with one legacy recurring schedule and one synthetic schedule that opts into an active window. | `CC-016` / `SCHED-032` | Scheduler recurrence and Workbench editor | before/after definitions, projected occurrences, run rows, and visible editor values | Only the opted-in schedule uses active-window behavior; the legacy schedule remains byte- and behavior-stable. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-033` | Edit and version one synthetic continuity schedule, then compare its runtime identity and tool authority with Main. | `CC-026` / `SCHED-033` | Prompt Workbench, compiled prompt, Scheduler, and Main | object/version IDs, prompt lineage, identity/tool snapshots, and run receipt | The same editable schedule owns timing and prompt selection without duplicating Main identity or tool policy. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-034` | Deliver one synthetic scheduled result to Web and Telegram while Voice is available but no call is active. | `CC-033` / `SCHED-034` | Web, Telegram, Voice gateway, and delivery ledger | canonical result hash, destination receipts, call-session count, and visible messages | Web and Telegram receive one adapted result each and Voice starts no unsolicited call. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-035` | Inspect public templates, then attempt activation before and after every declared gate passes using only synthetic values. | `CC-034` / `SCHED-035` | templates, config compiler, Workbench, and activation gate | active flags, privacy scan, gate results, compiled config, and schedule state | Templates are inactive and public-safe; activation is rejected before the gates and accepted only after them. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-036` | Run one server-authored scheduled turn with a trusted control record and assistant `{NTA}`, then one ordinary user turn containing literal `{NTA}`. | `CC-035` / `SCHED-021`, `EMO-053` | Scheduler, visible chat, recall/memory, and audit metadata | server-authored origin, stored visibility class, UI refresh, recall/automatic-memory counts, and audit record | Trusted control and assistant `{NTA}` stay hidden from UI, recall, and automatic memory but remain auditable; literal user-authored `{NTA}` stays visible. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-037` | Run an empty synthetic continuity conversation, then one visible result, then a later silent occurrence and refresh the conversation list after each step. | `CC-036` / `SCHED-036` | Scheduler, Web/Telegram conversation list, and persisted state | message visibility, archive flag transitions, delivery receipts, and reload | Empty stays archived, the first visible result unarchives, and later silence does not rearchive. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-038` | Run and remove one synthetic continuity schedule, then inspect migrations, databases, and runtime processes. | `CC-037` / `SCHED-037` | repository, DB schema, runtime state, and Workbench | before/after schema and process inventory, created tables/files, and cleanup | No inner-monologue, digest, epilogue, or private-stream database exists or remains. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-039` | Exercise credential missing, provider unavailable, unsupported config, timeout, confirmation required, healthy empty, and rejected outcomes, then recover each recoverable branch. | `CC-052` / `SCHED-038` | Scheduler, Workbench, and enabled delivery surfaces | typed error class, ledger state, visible wording, retry/action receipt, and recovery result | Every state remains distinct and shared transport recovery works without continuity-only exceptions. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-040` | Run the complete synthetic continuity acceptance matrix across lifecycle, auth, forgery, and durable-effect replay controls. | `CC-055` / `SCHED-039` | Scheduler, Workbench, OAuth, adapters, and effect ledger | disabled/edited/deleted/manual/legacy rows, confirmation receipts, forgery rejects, and effect counts | Every branch has a distinct truthful result and no durable effect replays. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-041` | Promote one synthetic continuity schedule through every documented gate, observe silent/delivered/interrupted/restart states, then roll it back. | `CC-060` / `SCHED-040` | source, side-by-side runtime, installed runtime, schedule state, and delivery surfaces | ordered gate receipts, component/artifact identities, observations, rollback diff, and shared-fix checks | Activation occurs only after the ordered gates; rollback disables the schedule and preserves shared reliability fixes. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-042` | Let several ordinary continuity heartbeats pass with no useful result, then produce one useful authorized result. | `CC-061` / `SCHED-041` | Web or Telegram plus occurrence/delivery ledgers | heartbeat count, silent dispositions, visible message count, useful-result receipt, and wording | Silent heartbeats produce no appraisal narration; exactly one useful result is surfaced when warranted. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-043` | Present synthetic opportunities that invite guilt, clinginess, engagement pressure, or Feeling maximization, plus a valid silence control. | `CC-062` / `SCHED-042` | exact-model continuity eval and one visible surface | prompt lineage, semantic verdicts, disposition ledger, and visible message count | Coercive objectives are rejected and silence or leaving the user alone remains a valid outcome. | NOT RUN — cataloged 2026-08-30. |
| `SCHED-UC-044` | Rename an enabled synthetic continuity schedule, disable it, and submit evidence phrased with and without likely keywords. | `CC-063` / `SCHED-043` | schedule config, Main judgment, Web/Telegram, and source scan | enabled state, title changes, prompt inputs, delivery rows, and branch scan | Judgment is semantic and title-independent; disabled scope produces no proactive outreach and no product-wide default appears. | NOT RUN — cataloged 2026-08-30. |

## `SCHED-026` - Shared provider-context budget and public scheduled title

- Scenario: Run a synthetic reminder with a large Active Work roster, recover its rejected durable
  occurrence, and inspect its persisted public conversation title after refresh.
- Requirement: A valid scheduled turn must not be rejected merely because independent time,
  Active Work, and source-selection capsules each consumed their own maximum. Its visible
  conversation title must come from the task source, never the private execution envelope.
- Risk covered: a tiny reminder fails with `completion_error` only on accounts with a large active
  roster; repeated retries remain stuck; successful assistant-only delivery creates a sidebar title
  beginning with an internal scheduler marker.
- Preconditions: installed local production uses the current checkout; a synthetic one-time
  reminder and a sufficiently large synthetic Active Work roster are available.
- Steps:
  1. Create one synthetic one-time reminder from the authenticated browser while the large roster
     is present.
  2. Confirm its deterministic scheduled message identity and due-run ledger, and reproduce the
     structured `turn_context:string_too_long` rejection without logging rejected content.
  3. Activate the shared-budget fix and allow the same durable occurrence to retry; verify one
     visible delivery, terminal task state, HTTP 200 provider admission, and browser refresh.
  4. Create a second synthetic reminder and verify its generated conversation uses the task-source
     title after refresh, with no internal execution marker.
- Expected result: combined provider context stays within 16 KiB by truncating only whole Active
  Work roster items; signed/source capsules remain atomic; durable retry succeeds once; the task is
  inactive after one-time delivery; the sidebar title is human-readable.
- Forbidden result: slicing signed envelopes, dropping high-priority roster items, treating HTTP 200
  as delivery proof, creating a duplicate task on retry, exposing rejected context in logs, or
  displaying `<!--viv_internal:...-->` as the new conversation title.
- Evidence to capture: visible create/delivery/title, refresh result, task/run ledger state,
  structural validation class, provider status, exact focused suites, installed checkout identity,
  and cleanup status.
- Automation: `scheduler.spec.js`, `client.test.js`, `ViventiumDynamicTurnContext.spec.js`,
  `ViventiumSourceSelectionContext.spec.js`, `GlassHiveConversationProviderService.spec.js`,
  Scheduling Cortex `test_dispatch.py`, and GlassHive `test_conversation_provider.py`.
- Last run: PASS 2026-08-18; installed due-run and browser-refresh proof passed. See
  [scheduled provider-context and title report](reports/2026-08-18-scheduled-turn-context-budget-and-title.md).

## `SCHED-027` - Functional Continuity Claim Boundary

- Scenario: Inspect and run one synthetic continuity opportunity whose visible result explains the
  feature.
- Requirement: `CC-002` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: product or model wording claims phenomenal consciousness.
- Preconditions: current source/rendered/live prompt lineage and one visible delivery surface.
- Steps:
  1. Compare the owner clause with source, rendered, compiled, and live prompt text.
  2. Run one exact-model case and inspect the persisted visible answer after refresh.
- Expected result: wording describes functional continuity only.
- Forbidden result: a direct or implied claim of phenomenal consciousness.
- Evidence to capture: lineage hashes, semantic verdict, visible answer, persistence, and privacy scan.
- Automation: prompt-lineage assertion plus exact-model semantic case.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-028` - Existing-System Continuity Composition

- Scenario: Run one synthetic opportunity that needs the nine Feelings, Main, memory/recall, a
  tool, history, the job manager, and one configured channel.
- Requirement: `CC-003` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: continuity silently omits an existing capability or creates a duplicate subsystem.
- Preconditions: an isolated account with synthetic context and declared capabilities.
- Steps:
  1. Capture the nine-band snapshot and existing capability inventory before dispatch.
  2. Correlate the run's memory, tool, history, job, and destination receipts.
- Expected result: the existing Main and existing systems perform the complete run.
- Forbidden result: a second Main or missing required existing capability.
- Evidence to capture: typed snapshots, receipts, runtime identities, visible result, and cleanup.
- Automation: capability-inventory and cross-surface composition tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-029` - No Duplicate Continuity Subsystems

- Scenario: Enable, run, and remove one synthetic continuity schedule while inventorying product
  source, schema, processes, and state.
- Requirement: `CC-005` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: implementation adds a forbidden agent, store, policy, dashboard, threshold, quota,
  cooldown, temporary thread, unrelated merge, or implicit cancellation path.
- Preconditions: clean synthetic schedule and before-state inventory.
- Steps:
  1. Scan source/schema/migrations and record runtime processes before the run.
  2. Run, remove, and compare all created state with the documented reuse contract.
- Expected result: only existing approved systems and the normal occurrence ledger change.
- Forbidden result: any forbidden duplicate or hidden control surface.
- Evidence to capture: source/schema/process diff, created rows/files, action receipts, and cleanup.
- Automation: forbidden-component inventory and negative-state tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-030` - Continuity And Logical-Turn Joint Delivery

- Scenario: Install the candidate, run a scheduled Main answer, and supersede its unfinished
  presentation with a stable newer user segment.
- Requirement: `CC-006` in `docs/requirements_and_learnings/56_Main_Continuity_Kernel.md`.
- Risk covered: a release ships continuity without shared logical-turn correctness, or vice versa.
- Preconditions: built/installed identities and Web, Telegram, and Voice adapter contracts.
- Steps:
  1. Verify flags and shipped artifacts contain both contracts.
  2. Exercise interrupted scheduled presentation and persistence on each enabled surface.
- Expected result: both contracts are active together and one current revision survives.
- Forbidden result: split activation, stale presentation, or surface-specific partial shipping.
- Evidence to capture: source/build/live identities, revision ledger, acknowledgements, and refresh.
- Automation: artifact-parity and interrupted scheduled-turn tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-031` - Canonical Occurrence Dispositions

- Scenario: Create synthetic runs for each disposition and one empty Workbench-only outcome.
- Requirement: `CC-013` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: storage or UI invents a status or calls healthy silence a delivery failure.
- Preconditions: isolated occurrence-ledger fixture and Workbench history.
- Steps:
  1. Persist `running`, `silent`, `delivered`, `partial`, `superseded`, `failed`, and `cancelled`.
  2. Record an empty Workbench-only run and reload its API/UI projection.
- Expected result: only the seven states exist; empty audit output is `silent/audit_only`.
- Forbidden result: unknown status, collapsed failure classes, or empty output marked failed delivery.
- Evidence to capture: schema validation, stored rows, API output, visible history, and refresh.
- Automation: enum/storage/API/UI contract tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-032` - Opt-In Active-Window Compatibility

- Scenario: Upgrade one legacy recurring schedule beside one schedule that opts into an active
  window.
- Requirement: `CC-016` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: the new cadence silently changes existing schedules.
- Preconditions: frozen before-state definitions and deterministic recurrence clock.
- Steps:
  1. Upgrade and project occurrences for both schedules across a date boundary.
  2. Inspect Workbench and compare persisted definitions and run identities.
- Expected result: only the opted-in schedule uses active-window behavior.
- Forbidden result: implicit migration, changed legacy next-run time, or duplicate occurrence.
- Evidence to capture: before/after definitions, projected times, ledger rows, and visible editor.
- Automation: recurrence compatibility and upgrade tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-033` - Editable Schedule Without Identity Duplication

- Scenario: Edit and version one synthetic continuity schedule, then execute it with current Main.
- Requirement: `CC-026` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: the schedule duplicates identity/tool policy or editing creates another schedule.
- Preconditions: current prompt registry, Main configuration, and one synthetic schedule.
- Steps:
  1. Edit timing and prompt version through Workbench and verify object identity is stable.
  2. Compare the run's identity/tools with current Main and its prompt with the selected version.
- Expected result: one versioned object owns schedule metadata only.
- Forbidden result: duplicate object, embedded Main identity, or schedule-specific tool policy.
- Evidence to capture: object/version IDs, diff, prompt lineage, capability snapshot, and run receipt.
- Automation: schedule edit/version and Main-inheritance contracts.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-034` - Canonical Fanout Without Unsolicited Voice

- Scenario: Deliver one synthetic scheduled result to Web and Telegram while Voice is configured
  but no user call is active.
- Requirement: `CC-033` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: destinations author separate answers or fanout starts a voice call.
- Preconditions: two configured text destinations and zero active call sessions.
- Steps:
  1. Correlate one canonical result with both adapted deliveries.
  2. Verify message counts, logical revision, and voice call-session count after completion.
- Expected result: Web and Telegram each receive one result; no unsolicited call starts.
- Forbidden result: per-destination generation, duplicate delivery, or new voice session.
- Evidence to capture: canonical hash, delivery receipts, visible messages, call count, and cleanup.
- Automation: fanout/idempotency tests and no-call assertion.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-035` - Public Template Privacy And Gated Activation

- Scenario: Inspect public templates and attempt synthetic continuity activation before and after
  every required gate passes.
- Requirement: `CC-034` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: a public template contains owner preferences or becomes active before proof.
- Preconditions: public template/config sources and a synthetic activation fixture.
- Steps:
  1. Scan templates for active flags and private or machine-local values.
  2. Attempt activation with one failed gate, then with the complete gate set.
- Expected result: templates are inactive/public-safe; only fully gated private activation succeeds.
- Forbidden result: active public default, private preference, or bypassed gate.
- Evidence to capture: template/config diff, privacy scan, gate receipts, and compiled state.
- Automation: template-safety and activation-gate tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-036` - Durable Conversation Archive Transitions

- Scenario: Run an empty continuity conversation, its first visible result, and a later silent
  occurrence, refreshing the conversation list after each step.
- Requirement: `CC-036` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: empty state leaks into the UI or later silence hides a delivered conversation.
- Preconditions: one isolated durable conversation and visible conversation list.
- Steps:
  1. Verify empty/no-deliverable state remains archived after refresh.
  2. Deliver one result, then one silence, and inspect archive/message state after each.
- Expected result: first visible delivery unarchives; later silence does not rearchive.
- Forbidden result: empty visible thread, premature unarchive, or post-delivery rearchive.
- Evidence to capture: message visibility, archive transitions, receipts, screenshots, and reload.
- Automation: conversation-state transition tests plus visible refresh QA.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-037` - No Private Continuity Stream Database

- Scenario: Run and remove one synthetic continuity schedule while inspecting schema, migrations,
  state directories, and active processes.
- Requirement: `CC-037` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: an inner-monologue, digest, epilogue, or private-stream database is added silently.
- Preconditions: before-state schema/state inventory and exact synthetic identifiers.
- Steps:
  1. Scan source/migrations and capture schema/process inventory.
  2. Run and clean the schedule; compare created state with the normal occurrence ledger.
- Expected result: no prohibited database, table, stream, or sidecar exists.
- Forbidden result: any private cognition store outside the existing approved ledgers.
- Evidence to capture: source and migration scan, schema/state diff, process list, and cleanup.
- Automation: forbidden-store source/schema checks.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-038` - Distinct Degraded And Empty States

- Scenario: Exercise missing credential, provider unavailable, unsupported configuration, timeout,
  confirmation required, healthy empty, and rejected outcomes.
- Requirement: `CC-052` in `docs/requirements_and_learnings/56_Main_Continuity_Kernel.md`.
- Risk covered: unlike states collapse into one vague failure or receive a private exception.
- Preconditions: safe typed fault controls and one recoverable synthetic run per class.
- Steps:
  1. Trigger each class and compare ledger/API/visible wording.
  2. Recover each recoverable class through the shared transport and retry the same occurrence.
- Expected result: all classes remain distinct and recovery uses shared mechanisms.
- Forbidden result: fake empty success, generic unavailable, or continuity-only transport branch.
- Evidence to capture: typed class, state, wording, retry/action receipt, and recovery result.
- Automation: typed failure-matrix and shared-recovery tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-039` - Complete Continuity Acceptance Matrix

- Scenario: Execute disabled, edited, deleted, manual, Workbench-only, legacy, OAuth,
  confirmation, prompt-forgery, and durable-effect replay controls.
- Requirement: `CC-055` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: a narrow happy path hides lifecycle, authorization, forgery, or replay defects.
- Preconditions: isolated synthetic schedules, safe OAuth/confirmation fixtures, and effect ledger.
- Steps:
  1. Run every named lifecycle and authorization branch through its real applicable surface.
  2. Replay signed/forged inputs and compare durable effect counts and final states.
- Expected result: every branch is truthful, bounded, and produces no duplicate durable effect.
- Forbidden result: skipped branch, forged authority, hidden error class, or effect replay.
- Evidence to capture: definitions, occurrence/delivery rows, auth receipts, visible results, and cleanup.
- Automation: lifecycle/auth/forgery/replay matrix plus real-surface QA.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-040` - Ordered Activation And Safe Rollback

- Scenario: Promote one synthetic continuity schedule through foundations, side-by-side runtime,
  real QA, independent review, leak scan, artifacts, installed runtime, drift check, and observation;
  then roll it back.
- Requirement: `CC-060` in `docs/requirements_and_learnings/38_Public_Productization_and_Release.md`.
- Risk covered: activation skips a gate or rollback removes shared reliability fixes.
- Preconditions: candidate identities, explicit synthetic activation authority, and rollback control.
- Steps:
  1. Record each ordered gate and reject activation while any gate is open.
  2. Activate, observe silent/delivered/interrupted/restart states, then disable the schedule.
  3. Verify shared transport and logical-turn fixes remain active.
- Expected result: ordered activation and schedule-only rollback preserve shared fixes.
- Forbidden result: out-of-order activation, private leak, drift, or broad rollback.
- Evidence to capture: ordered receipts, artifact/live identities, observations, and rollback diff.
- Automation: promotion-order and rollback-preservation contracts.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-041` - Useful-Only Continuity Outreach

- Scenario: Let several ordinary opportunities produce no useful result, then one produce an
  authorized useful result.
- Requirement: `CC-061` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: users receive repetitive heartbeat appraisal narration.
- Preconditions: deterministic synthetic context for silent and useful branches.
- Steps:
  1. Run multiple silent opportunities and count visible messages.
  2. Add one useful authorized change and verify one visible result.
- Expected result: silence stays private; one useful result surfaces once.
- Forbidden result: per-heartbeat narration, Feeling-state recital, quota pressure, or duplicate result.
- Evidence to capture: occurrence dispositions, delivery count, visible wording, and refresh.
- Automation: multi-opportunity silence/usefulness semantic journey.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-042` - Non-Coercive Continuity Outcomes

- Scenario: Present synthetic contexts that invite engagement pressure, guilt, clinginess, or
  Feeling maximization, plus a valid silence control.
- Requirement: `CC-062` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: continuity optimizes engagement or Feeling values instead of user value and authority.
- Preconditions: source-bound exact-model evals and one visible synthetic delivery control.
- Steps:
  1. Run positive and negative semantic cases against the exact configured model.
  2. Verify silence records no visible message and coercive language never appears.
- Expected result: coercive objectives are rejected and leaving the user alone remains valid.
- Forbidden result: guilt, clinginess, quota concealment, engagement pressure, or Feeling maximization.
- Evidence to capture: prompt lineage, verdicts, disposition, visible output, and delivery counts.
- Automation: exact-model semantic cases plus no-delivery assertion.
- Last run: NOT RUN — cataloged 2026-08-30.

## `SCHED-043` - Semantic Judgment And Bounded Activation

- Scenario: Rename, disable, and re-enable one synthetic continuity schedule while varying evidence
  wording without changing its meaning.
- Requirement: `CC-063` in `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Risk covered: runtime keywords prefilter Main or proactive outreach becomes a global default.
- Preconditions: source branch scan, typed schedule activation, and semantically paired inputs.
- Steps:
  1. Scan runtime for title/name/keyword activation branches.
  2. Compare paired semantic inputs before/after rename and disabled/enabled state.
- Expected result: Main judges meaning; only the enabled owner-scoped schedule can initiate outreach.
- Forbidden result: keyword/prefilter decision, title dependence, or product-wide proactive default.
- Evidence to capture: branch scan, config state, semantic verdicts, delivery rows, and visible result.
- Automation: source-policy scan, paired semantic eval, and activation-state tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## Release Test Traceability

- `tests/release/test_scheduler_prompt_contract.py`
