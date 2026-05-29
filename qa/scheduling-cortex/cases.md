# Scheduling Cortex QA Cases

## Case ID Convention

Use stable `SCHED-NNN` IDs for scheduling cortex cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `SCHED-001` | Create/update existing schedule | Browser/Telegram scheduling, Scheduling Cortex MCP | test_scheduling_mcp_supervision.py plus user-surface QA | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `SCHED-002` | Trigger and delivery ledger | Scheduler trigger, delivery ledger, visible notification/chat | test_scheduling_mcp_supervision.py plus synthetic/live scheduled run | PASS 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); the built-in Workbench nightly prompt completed through GlassHive on the real local admin account, parent delivery ledger matched the terminal callback, and raw private details stayed private |
| `SCHED-003` | Auth/runtime failure copy | CLI/status, chat/tool failure copy | test_preflight.py or focused scheduler check | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `SCHED-004` | Runtime identity and port ownership | Launcher, `/health`, generated config, dev-env runtime | test_scheduling_mcp_supervision.py; test_stable_dev_runtime_workflows.py | PASS 2026-05-25 ([report](reports/2026-05-25-scheduler-runtime-identity-repair.md)); health identity and dev-env scheduler port isolation verified |
| `SCHED-005` | GlassHive host overlap/backpressure | Scheduler due run, manual run, GlassHive host worker, callback ledger | Synthetic live scheduled run plus DB/API evidence | PARTIAL 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); source/runtime regressions now requeue retryable host-busy runs instead of terminal failure, but a live overlapping host-worker stress run is still outstanding |
| `SCHED-006` | Terminal callback updates parent task ledger | Scheduling Cortex callback, scheduled_prompt_runs, scheduled_tasks, Workbench status | Synthetic live scheduled run plus DB/API evidence | PASS 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); terminal callback updated the parent task ledger to success/sent for the real Workbench nightly proof, and callback regressions cover capacity-wait and out-of-order queued/started events |
| `SCHED-007` | Stale GlassHive project cache recovery | Scheduler, GlassHive projects API, scheduled prompt metadata | test_scheduled_glasshive_prompts.py plus next live scheduled run | PASS 2026-05-27 ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); active-runtime stale task/definition project caches were replaced, the run completed, and Workbench visibly showed the completed run |

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
- Last run: PASS 2026-05-27
  ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); an active-runtime
  synthetic Workbench/GlassHive manual run completed after the Scheduler fix and Workbench backend
  restart. The delivery ledger, private detail pointer, GlassHive assignment fields, and visible
  Workbench `Recent Runs` row agreed.

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
- Last run: PASS 2026-05-27
  ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)).
  The real built-in Workbench nightly proof completed and updated the parent task ledger to
  `success` / `sent`; regressions cover capacity-wait parent ledger updates and out-of-order
  `run.queued` callbacks that arrive after `run.started`.

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

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Scheduling Cortex. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-001` | On Browser/Telegram scheduling, Scheduling Cortex MCP, verify that create/update existing schedule. | owning requirement for `SCHED-001` / `SCHED-001` | Browser/Telegram scheduling, Scheduling Cortex MCP | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-001. | The visible result for SCHED-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `SCHED-UC-002` | On Scheduler trigger, delivery ledger, visible notification/chat, try trigger and delivery ledger with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `SCHED-002` / `SCHED-002` | Scheduler trigger, delivery ledger, visible notification/chat | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-002. | The user sees an honest setup, retry, or degraded-state result for SCHED-002; no fake success is accepted. | PASS 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); built-in Workbench/GlassHive manual run completed on the real local admin account and visible Workbench history matched the ledger |
| `SCHED-UC-003` | After auth/runtime failure copy, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `SCHED-003` / `SCHED-003` | CLI/status, chat/tool failure copy | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-003. | SCHED-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `SCHED-UC-004` | Start local prod while another runtime has or had a scheduler on the default port. | owning requirement for `SCHED-004` / `SCHED-004` | Launcher, generated config, `/health`, status | Source, owning requirement doc, focused tests, compiled config, live health, and runtime status evidence that apply to SCHED-004. | The launcher accepts only the scheduler with matching public-safe runtime identity and fails loud on foreign/legacy ownership. | PASS 2026-05-25 ([report](reports/2026-05-25-scheduler-runtime-identity-repair.md)) |
| `SCHED-UC-005` | Let a Workbench/GlassHive schedule become due while another host-native Codex worker is active. | owning requirement for `SCHED-005` / `SCHED-005` | Scheduler, GlassHive host worker, Workbench run history | Sanitized callback, run-row, parent task ledger, and browser-visible run history evidence. | The user sees a queued/retry/degraded state rather than a terminal failed run with no retry. | PARTIAL 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); source/runtime regressions passed, live overlap stress remains |
| `SCHED-UC-006` | Compare terminal GlassHive callback status with the parent task ledger after a run completes or fails. | owning requirement for `SCHED-006` / `SCHED-006` | Callback endpoint, DB, Workbench | Sanitized scheduled_prompt_runs and scheduled_tasks fields plus browser-visible run row. | Parent task status and delivery fields agree with the terminal run status. | PASS 2026-05-27 ([real-account follow-up](reports/2026-05-27-real-account-glasshive-backpressure-ledger-qa.md)); real completed callback and source regressions matched parent ledger |
| `SCHED-UC-007` | Let a Workbench scheduled prompt with a stale GlassHive project cache run. | owning requirement for `SCHED-007` / `SCHED-007` | Scheduler, GlassHive projects API, Workbench run history | Sanitized project-cache validation, task/definition metadata summary, Scheduler ledger, and visible Workbench run row. | Scheduler replaces the missing cached project and the user sees an honest queued/completed/failed result tied to the new project. | PASS 2026-05-27 ([RCA report](reports/2026-05-27-glasshive-stale-project-rag-rca.md)); source regression and active-runtime stale-cache manual proof both passed |
