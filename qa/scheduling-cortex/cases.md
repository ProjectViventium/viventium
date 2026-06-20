# Scheduling Cortex QA Cases

## Case ID Convention

Use stable `SCHED-NNN` IDs for scheduling cortex cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `SCHED-001` | Create/update existing schedule | Browser/Telegram scheduling, Scheduling Cortex MCP | test_scheduling_mcp_supervision.py plus user-surface QA | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `SCHED-002` | Trigger and delivery ledger | Scheduler trigger, delivery ledger, visible notification/chat | test_scheduling_mcp_supervision.py plus synthetic/live scheduled run | PASS-CORRECTNESS/LONG-DURATION 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); built-in Workbench task carried bounded `catch_up` misfire policy, Jun 11 delivery ledger completed through GlassHive/callback/Workbench, and focused regressions passed |
| `SCHED-003` | Auth/runtime failure copy | CLI/status, chat/tool failure copy | test_preflight.py or focused scheduler check | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `SCHED-004` | Runtime identity and port ownership | Launcher, `/health`, generated config, dev-env runtime | test_scheduling_mcp_supervision.py; test_stable_dev_runtime_workflows.py | PASS 2026-05-25 ([report](reports/2026-05-25-scheduler-runtime-identity-repair.md)); health identity and dev-env scheduler port isolation verified |
| `SCHED-005` | GlassHive host overlap/backpressure | Scheduler due run, manual run, GlassHive host worker, callback ledger | Synthetic live scheduled run plus DB/API evidence | PARTIAL 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); source/runtime regressions now requeue retryable host-busy runs instead of terminal failure, but a live overlapping host-worker stress run is still outstanding |
| `SCHED-006` | Terminal callback updates parent task ledger | Scheduling Cortex callback, scheduled_prompt_runs, scheduled_tasks, Workbench status | Synthetic live scheduled run plus DB/API evidence | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); latest due built-in run had matching child run, GlassHive run, terminal callback, parent ledger success/sent, and visible Workbench completed row |
| `SCHED-007` | Stale GlassHive project cache recovery | Scheduler, GlassHive projects API, scheduled prompt metadata | test_scheduled_glasshive_prompts.py plus next live scheduled run | PASS 2026-05-27 ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); active-runtime stale task/definition project caches were replaced, the run completed, and Workbench visibly showed the completed run |
| `SCHED-008` | GlassHive host runtime dependency surfacing and safe recovery | Scheduler dispatch, GlassHive runtime preflight, generated env | test_scheduled_glasshive_prompts.py, test_config_compiler.py, test_preflight.py, live no-run host preflight | PASS 2026-05-30 ([RCA report](reports/2026-05-30-glasshive-host-runtime-dependency-rca.md), [nightly gaps follow-up](reports/2026-05-30-nightly-gaps-repair-followup.md)); structured `runtime_dependency_missing` is preserved, generated env emits the Codex binary path and GlassHive DB path, Codex.app discovery covers system/user app roots plus override, and safe scheduler recovery to docker is regression-covered |
| `SCHED-009` | Callback outbox bounded termination and health gate | GlassHive callback outbox, scheduler delivery ledger, metrics | GlassHive callback regressions plus nightly DB/API outbox-health probe | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); GlassHive had 0 pending/delivering callbacks, latest Jun 11 callbacks delivered in one attempt, and only 2 historical May dead-letter rows |
| `SCHED-010` | Built-in nightly reflection is seeded for the installing local admin without personal identity drift. | Prompt Workbench first-admin seed, Scheduler task row, GlassHive executor metadata | `test_prompt_workbench.py`, `test_default_nightly_routines.py`, install/upgrade generated-env QA | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); generated/runtime defaults, focused regressions, active Scheduler row, and Workbench browser evidence show the built-in nightly is active through `glasshive_host` without hardcoded user identity |
| `SCHED-011` | Orphaned user schedules stop retrying forever | Scheduler failure ledger, active flag, user ownership | `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/tests/test_scheduler.py` plus sanitized DB audit | PASS 2026-06-02; regression proves structured `scheduler/chat` `user_not_found` deactivates the task, preserves failed ledger evidence, and leaves transient/account-repair failures active; live cleanup retired three pre-fix active orphan rows |
| `SCHED-012` | Built-in nightly catch-up after a late scheduler tick | Scheduler misfire policy, Workbench task metadata, GlassHive callback, visible Workbench run history | `test_scheduled_glasshive_prompts.py::test_builtin_workbench_nightly_misfire_policy_catches_up_late_run` plus a future live delayed-tick proof | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); synthetic regression passed and Jun 11 live due run started inside grace, while delayed-tick proof beyond normal grace remains a separate future proof |
| `SCHED-013` | Scheduled agent runs use deterministic due-date context and do not drift day labels from prior same-conversation briefings | Scheduler dispatch, LibreChat scheduler gateway, Telegram/web delivery ledger | `test_dispatch.py`, `surfacePrompts.spec.js`, `test_config_compiler.py`, synthetic live scheduled run with Telegram/computer-use evidence | ADDED 2026-06-15; run with the scheduled-date-grounding fix |

## `SCHED-001` - Create/update existing schedule

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
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `SCHED-002` - Trigger and delivery ledger

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
- Last run: PASS/REPAIRED 2026-06-07
  ([repair follow-up](../memory-hardening/reports/2026-06-07-nightly-repair-follow-up.md)); the
  built-in `Subconscious Deep Thought` task is active, due next at `2026-06-08T10:00:00Z`, and now
  carries bounded catch-up metadata so a late scheduler tick within 12 hours queues delivery instead
  of losing the run as `misfire_grace_exceeded`. The Jun 7 run completed through Scheduler,
  GlassHive, callback, and Workbench visible run history.

## `SCHED-003` - Auth/runtime failure copy

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
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `SCHED-004` - Runtime identity and port ownership

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
- Last run: PASS 2026-05-25
  ([report](reports/2026-05-25-scheduler-runtime-identity-repair.md)).

## `SCHED-005` - GlassHive host overlap/backpressure

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
- Last run: PASS with significant performance regression 2026-06-05
  ([nightly review](../memory-hardening/reports/2026-06-05-nightly-routines-health-review.md)).
  The June 5 built-in Workbench proof had matching terminal callback, child run, parent ledger,
  GlassHive run, and visible Workbench state. The due run started at `2026-06-05T10:00:09Z` and
  completed at `2026-06-05T13:07:10Z`, which is complete but slow versus the recent baseline.

## `SCHED-007` - Stale GlassHive project cache recovery

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
- Last run: PASS 2026-06-05
  ([nightly review](../memory-hardening/reports/2026-06-05-nightly-routines-health-review.md)).
  GlassHive metrics and callback DB aggregates showed no active callback backlog, no queued/active
  runs, active max attempts 0, newest built-in callback delivered in one attempt, and only bounded
  historical dead-letter audit rows.

## `SCHED-010` - Installer Scheduler Readiness Row

- Requirement: Express Rich Brain Readiness must expose Scheduler as a first-class installed
  surface, not an implicit Workbench detail.
- Risk covered: installer/status QA misses due schedules, delivery ledger, callback proof, or stale
  failed rows because Scheduler is not visible in the readiness model.
- Preconditions: generated runtime env and scheduler SQLite state are available with synthetic or
  sanitized rows.
- Steps:
  1. Compile an Express-shaped config and confirm scheduler env keys are generated.
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
- Last run: PASS/REPAIRED 2026-06-07
  ([repair follow-up](../memory-hardening/reports/2026-06-07-nightly-repair-follow-up.md));
  install/status, live Scheduler ledger, and Workbench browser inspection agree for the built-in
  nightly reflection. Separate clean-machine installer proof remains an installer release gate, not
  a blocker for the repaired owner-runtime nightly workflow.

## `SCHED-011` - Orphaned User Schedule Retirement

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
- Last run: PASS/PARTIAL 2026-06-11
  ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md));
  regression covers the escaped Jun 6 late timing and Jun 11 live due run started inside normal
  grace and completed through the normal chain, but live delayed-tick catch-up beyond normal grace
  remains a future QA gate.

## `SCHED-013` - Scheduled Run Date Grounding

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
- Last run: ADDED 2026-06-15; execute with the implementation QA run.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Scheduling Cortex. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-001` | On Browser/Telegram scheduling, Scheduling Cortex MCP, verify that create/update existing schedule. | owning requirement for `SCHED-001` / `SCHED-001` | Browser/Telegram scheduling, Scheduling Cortex MCP | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-001. | The visible result for SCHED-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `SCHED-UC-002` | On Scheduler trigger, delivery ledger, visible notification/chat, try trigger and delivery ledger with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `SCHED-002` / `SCHED-002` | Scheduler trigger, delivery ledger, visible notification/chat | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-002. | The user sees an honest setup, retry, or degraded-state result for SCHED-002; no fake success is accepted. | PASS-CORRECTNESS/LONG-DURATION 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); Jun 11 built-in Workbench run completed and duration remains a watch item |
| `SCHED-UC-003` | After auth/runtime failure copy, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `SCHED-003` / `SCHED-003` | CLI/status, chat/tool failure copy | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-003. | SCHED-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `SCHED-UC-004` | Start local prod while another runtime has or had a scheduler on the default port. | owning requirement for `SCHED-004` / `SCHED-004` | Launcher, generated config, `/health`, status | Source, owning requirement doc, focused tests, compiled config, live health, and runtime status evidence that apply to SCHED-004. | The launcher accepts only the scheduler with matching public-safe runtime identity and fails loud on foreign/legacy ownership. | PASS 2026-05-25 ([report](reports/2026-05-25-scheduler-runtime-identity-repair.md)) |
| `SCHED-UC-005` | Let a Workbench/GlassHive schedule become due while another host-native Codex worker is active. | owning requirement for `SCHED-005` / `SCHED-005` | Scheduler, GlassHive host worker, Workbench run history | Sanitized callback, run-row, parent task ledger, and browser-visible run history evidence. | The user sees a queued/retry/degraded state rather than a terminal failed run with no retry. | PARTIAL 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); source/runtime regressions passed, live overlap stress remains |
| `SCHED-UC-006` | Compare terminal GlassHive callback status with the parent task ledger after a run completes or fails. | owning requirement for `SCHED-006` / `SCHED-006` | Callback endpoint, DB, Workbench | Sanitized scheduled_prompt_runs and scheduled_tasks fields plus browser-visible run row. | Parent task status and delivery fields agree with the terminal run status. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); Jun 11 terminal callback, child run, parent ledger, GlassHive run, and visible Workbench state matched |
| `SCHED-UC-007` | Let a Workbench scheduled prompt with a stale GlassHive project cache run. | owning requirement for `SCHED-007` / `SCHED-007` | Scheduler, GlassHive projects API, Workbench run history | Sanitized project-cache validation, task/definition metadata summary, Scheduler ledger, and visible Workbench run row. | Scheduler replaces the missing cached project and the user sees an honest queued/completed/failed result tied to the new project. | PASS 2026-05-27 ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); source regression and active-runtime stale-cache manual proof both passed |
| `SCHED-UC-008` | Let a Workbench/GlassHive scheduled dispatch encounter a host runtime dependency blocker before `/assign`. | owning requirement for `SCHED-008` / `SCHED-008` | Scheduler, generated env, GlassHive host preflight | Sanitized structured error class, generated env key summary, safe recovery branch result, and no-run host preflight DB proof. | The user/admin sees the real dependency class, the fixed runtime accepts host `codex-cli` without creating a run, or the same task safely recovers to sandbox/workstation mode before terminal failure. | PASS 2026-05-30 ([RCA report](reports/2026-05-30-glasshive-host-runtime-dependency-rca.md), [nightly gaps follow-up](reports/2026-05-30-nightly-gaps-repair-followup.md)); structured error preservation, safe recovery regression, and live no-run host preflight passed |
| `SCHED-UC-009` | Inspect callback outbox health after scheduled Workbench/GlassHive delivery. | owning requirement for `SCHED-009` / `SCHED-009` | GlassHive metrics, callback outbox DB, Workbench run history | Sanitized callback status counts, before/after dead-letter delta, oldest pending age, active max attempts, terminal dead-letter count, and latest scheduled run ledger. | Latest delivery can succeed only if the delivery substrate also has no unexplained stale/high-attempt pending callback rows and no fresh dead-letter delta. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); callback outbox had no active backlog or fresh high-attempt pending rows, latest built-in callbacks delivered in one attempt, and 2 historical May dead-letter rows remain watch-only |
| `SCHED-UC-010` | Inspect Scheduler readiness immediately after Express install or upgrade. | `39_Installer_and_Config_Compiler.md` / `SCHED-010`, `INST-004` | `bin/viventium status`, scheduler health endpoint, scheduler SQLite ledger, Workbench run history | Sanitized endpoint result, DB count/status/outcome/next-run summary, generated env keys, focused tests. | Scheduler is visible as installed/configured/running/degraded with a concrete next action and no private schedule data in public output. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); built-in scheduler ledger/browser evidence agree, while broader status needs user-level Anthropic reconnect for later non-overnight rows |
| `SCHED-UC-011` | Let a recurring task fail because its owner user no longer exists. | `11_Scheduling_Cortex.md` / `SCHED-011` | Scheduler failure ledger, active flag, sanitized DB audit | Focused scheduler regression plus hash/truncated live DB evidence. | The orphaned task becomes inactive with `orphaned_user_not_found` ledger evidence; non-orphan auth/provider failures are not hidden. | PASS 2026-06-02; focused regression passed, live audit classified orphan rows separately from provider reconnect rows, and three pre-fix orphan rows were retired from active state |
| `SCHED-UC-012` | Let the built-in nightly Workbench reflection be processed late but inside the catch-up window. | `11_Scheduling_Cortex.md` / `SCHED-012`, `PW-029` | Scheduler loop, GlassHive, Workbench run history | Sanitized late timing, child/parent ledger fields, GlassHive callback, visible Workbench row. | The late built-in routine runs once, records lateness, advances to the next period, and Workbench shows completed. | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); synthetic regression passed and Jun 11 live run started inside grace, while delayed-tick proof beyond normal grace remains outstanding |
| `SCHED-UC-013` | Receive a scheduled morning-style briefing through Telegram/web after prior same-conversation dated briefings exist. | `11_Scheduling_Cortex.md` / `SCHED-013` | Scheduler, Telegram/computer-use, delivery ledger, Mongo/tool-call state | Sanitized scheduled run context, opening date label, date-guard status, tool/cortex evidence count/classification, logs, and persisted message summary. | The visible briefing is anchored to the due local date and does not assert unverified calendar/email/task facts. | ADDED 2026-06-15; run with SCHED-013 implementation QA |
