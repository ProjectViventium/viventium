# SCHED-002 / PW-029 Live Delivery QA - 2026-05-25

## Status

- `SCHED-002` trigger and delivery ledger: `PARTIAL`
- `PW-029` scheduled GlassHive prompts: `PARTIAL`
- `SCHED-005` GlassHive host overlap/backpressure: `FAIL`
- `SCHED-006` terminal callback parent-ledger parity: `FAIL`
- `PW-032` one-time scheduled prompt state parity: `FAIL`

The base local-prod scheduler ownership repair held: `localhost:7110/health` returned the
identity-bearing local-prod scheduler, Workbench was reachable, and the scheduler processed due
synthetic prompts. The remaining gaps are no longer theoretical.

## Public-Safe QA Inputs

All live QA used synthetic Workbench-private scheduled prompts with memory write mode `off`.
Synthetic prompts explicitly instructed the worker not to inspect or mutate private memories,
conversations, email, files, accounts, or memory proposals. Synthetic definitions were disabled
after QA so they remain visible only as inert evidence rows.

Raw prompt bodies, local paths, token-bearing URLs, private schedule titles, private run detail
files, and screenshots are intentionally omitted.

## Evidence Checked

- Scheduling Cortex `/health`: identity-bearing local-prod scheduler response.
- Scheduler DB summary:
  - active overdue count was `0` after the ownership repair.
  - the previously stale Workbench nightly task advanced to the next scheduled day as `missed`
    rather than replaying the skipped outage window.
- Workbench API:
  - synthetic manual run returned a scheduled prompt run with a GlassHive run id and private detail
    pointer.
  - synthetic due-only run appeared in Workbench run history as `completed`.
  - synthetic overlap run appeared in Workbench run history as `failed`.
- Callback/private-detail summaries:
  - manual synthetic run received `run.queued`, `run.started`, then `run.completed`.
  - due-only synthetic run received `run.started`, then `run.completed`.
  - overlap synthetic run received `run.failed`; the callback message stated the host-native
    Codex CLI family already had an active worker.
- Playwright:
  - Workbench loaded with no console errors.
  - Prompt Flow showed the synthetic scheduled prompt rows.
  - The Schedules panel for the due-only synthetic row showed `Recent Runs -> completed` and
    `GlassHive run completed. Private details are stored in the run detail file.`

## Results

### Manual Workbench / GlassHive Run

Result: `PASS`

- Created a synthetic Workbench-private prompt.
- Triggered manual `Run GlassHive`.
- Run transitioned `queued -> running -> completed`.
- Run history displayed completion in the Workbench Schedules panel.
- No memory proposal files appeared for the synthetic run.

### Due-Only Scheduler Trigger

Result: `PASS` for the isolated due path.

- Created a synthetic one-time Workbench/GlassHive schedule due shortly after creation.
- Scheduler fired the due task.
- GlassHive host run started and completed.
- DB/API evidence showed a completed scheduled prompt run with private detail pointer.
- Browser evidence showed the completed run in Workbench Recent Runs.

### Overlap / Backpressure

Result: `FAIL`

- A synthetic manual GlassHive host worker was active.
- A second synthetic one-time Workbench/GlassHive schedule became due while that worker was active.
- Scheduler reached GlassHive and created a run row, but the callback terminally failed almost
  immediately.
- Callback message indicated host-native Codex CLI allows one active host worker per CLI family.
- There was no durable queued/retry/backpressure state for the due scheduled run.

Impact: if a nightly scheduled prompt fires while another host-native Codex/GlassHive worker is
active, the scheduled run can fail instead of waiting or retrying.

### Parent Task Ledger Parity

Result: `FAIL`

- The overlap run row was `failed`.
- The parent `scheduled_tasks` row still showed `last_status=success`.

Impact: diagnostics and Workbench status can claim the scheduler task succeeded while the actual
scheduled prompt run failed.

### One-Time Schedule UI State

Result: `FAIL`

- After a fired one-time synthetic schedule completed, the backing task was inactive with no next
  run.
- Workbench still showed the definition row as enabled with no next run before cleanup.
- The Schedules editor displayed the fired one-time schedule as a daily `03:00` schedule rather
  than preserving or clearly labeling one-time state.

Impact: a user can misread a completed one-time schedule as an enabled recurring schedule, or save
  it back as the wrong schedule type.

## Misalignments

1. `scheduled_prompt_runs.status` can disagree with `scheduled_tasks.last_status`.
2. Workbench uses definition-level `active` for the visible row even when the task-level schedule
   has completed and gone inactive.
3. Workbench editor supports daily/weekdays/weekly/cron, while API/runtime can store one-time
   schedules.
4. GlassHive host-worker capacity is not modeled as scheduler backpressure or retryable state.
5. The repaired scheduler advanced stale recurring rows as missed, so the missed overnight run was
   not replayed. The expected catch-up policy for this class of missed nightly Workbench run still
   needs an explicit source-of-truth check.

## Recommended Fix Plan

1. Add a Scheduling Cortex/Workbench host-worker backpressure contract:
   - detect active host-native GlassHive runs using the existing worker-family and configured
     per-user/per-tenant worker limits rather than a hard-coded provider string,
   - mark the new scheduled run as waiting/retryable rather than terminal failed,
   - retry after the active run completes or after a bounded delay,
   - add a regression for manual+due overlap.
2. Update the terminal callback handler to propagate `run.completed` and `run.failed` into the
   parent task ledger:
   - completed callback keeps/sets parent task success,
   - failed callback can downgrade a previously successful scheduler-trigger ledger to failed
     delivery state,
   - Workbench should surface the terminal run status without contradiction.
3. Fix Workbench one-time schedule parity:
   - either support `once` in the editor or render it read-only with an explicit completed/one-time
     state,
   - compute visible active state from the backing task's `active` and `next_run_at` state when
     that state is terminal,
   - prevent saving a one-time schedule as daily unless the user changes it intentionally.
4. Add synthetic QA coverage:
   - isolated due completion,
   - manual run completion,
   - due run while host worker active,
   - failed callback parent-ledger parity,
   - one-time schedule UI state.
5. Recheck missed-nightly catch-up policy and sanitized error handling:
   - confirm whether skipped Workbench nightly runs should replay, be marked missed, or require
     manual catch-up,
   - ensure public/API-visible failure summaries do not expose local filesystem paths or private
     runtime detail.

## Claude Review

ClaudeViv review-only pass completed after the live evidence was gathered and after the provisional
RCA was written. It confirmed the `PARTIAL` / `FAIL` classifications and raised five fix constraints
that are now folded into the plan:

- callback handling must allow asynchronous terminal failures to downgrade a parent ledger that was
  optimistically marked success when dispatch started;
- backpressure must honor configured worker capacity by user/tenant and worker family, not a literal
  `codex-cli` string;
- Workbench one-time visibility should derive from backing task state, especially `active` and
  `next_run_at`;
- the stale real nightly row needs a separate catch-up-policy decision before it is treated as
  expected behavior;
- regression coverage should include async callback-after-dispatch, downstream visible status, and
  public-safe error sanitization.

## Cleanup

Synthetic due rows were disabled after QA. No owner memories, conversations, transcript content,
email, or private scheduled prompt bodies were written into public repo artifacts.
