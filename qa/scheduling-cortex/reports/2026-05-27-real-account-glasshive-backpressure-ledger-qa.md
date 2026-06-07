<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Real-Account Workbench Nightly GlassHive QA - 2026-05-27

## Verdict

`PASS` for the real-account Workbench nightly delivery path that was previously blocked by stale
GlassHive project cache and callback-ledger drift.

`PARTIAL` remains for live host-overlap stress (`SCHED-005`): the product fix and source/runtime
regressions now requeue retryable host-worker contention instead of marking the run terminal failed,
but a live overlapping host-native worker proof was not run in this pass.

## What Was Missed

The earlier follow-up proved the stale-project-cache repair with a synthetic Workbench prompt, but
did not rerun the built-in real-account schedule. The real-account manual run then exposed a separate
GlassHive backpressure bug: `host_worker_busy` was classified as retryable, but the service finalized
it as terminal `failed` and emitted `run.failed`. A second gap left the parent `scheduled_tasks`
ledger carrying stale failure/success state after callbacks updated `scheduled_prompt_runs`.

ClaudeViv review-only pass agreed with this RCA and added two important constraints:

- do not wait invisibly inside the host runtime after `run.started`; keep a visible queued/retry
  state instead;
- redact raw GlassHive worker ids from callback/user-visible failure text.

## Fix Implemented

- GlassHive store now persists retry metadata (`retry_after`, `retry_attempts`,
  `last_retry_class`) and claim logic ignores queued runs until their retry time.
- GlassHive service now checks host-worker capacity before emitting `run.started`; retryable
  `host_worker_busy` runs are requeued with backoff and `run.waiting_on_capacity` instead of
  terminal `run.failed`.
- Runtime race protection remains in `_acquire_host_slot`; the preflight check is only an honest
  ledger optimization.
- Public callback text and failure diagnostics redact raw GlassHive worker/project/run ids.
- Scheduling Cortex callback handling now updates the parent task delivery ledger for terminal and
  capacity-wait callbacks.
- Scheduling Cortex no longer downgrades a `running` Workbench run back to `queued` when an older
  `run.queued` callback is delivered after `run.started`.

## Real Account Evidence

Private values are omitted. Raw account email, user id, prompt text, memory context, project ids,
worker ids, run ids, local paths, tokens, and private detail file contents were not written here.

- Workbench loopback auth resolved to the expected real local admin account; only account hashes were
  inspected privately.
- Built-in schedule: `Subconscious Deep Thought`, active, `glasshive_host`.
- Manual real-account trigger returned queued delivery with reason `glasshive_host_run_queued`.
- GlassHive run event sequence for the matched scheduled run: `run.queued`, `run.started`,
  `run.completed`.
- GlassHive matched run state: `completed`; `failure_class=""`; `failure_retryable=0`;
  `retry_attempts=0`.
- All three matched GlassHive callbacks delivered successfully: `run.queued`, `run.started`,
  `run.completed`.
- Scheduling Cortex `scheduled_prompt_runs.status=completed`, `error_class=NULL`, and result summary
  was the public-safe private-detail summary.
- Parent `scheduled_tasks.last_status=success`, `last_error=NULL`,
  `last_delivery_outcome=sent`, and `last_delivery_reason` matched the completed callback summary.
- Workbench UI browser QA selected the built-in schedule and verified the visible `Recent Runs`
  panel showed a completed run before older failed rows. No screenshot was saved because the pane can
  contain private/local content.
- Runtime health after restart: GlassHive API healthy, Scheduling Cortex healthy, active GlassHive
  runs `0`. A later interrupted non-scheduled GlassHive run was confirmed not to match any
  `scheduled_prompt_runs` row.

## Tests Run

```text
cd viventium_v0_4/GlassHive/runtime_phase1
uv run pytest tests/test_api.py::test_retryable_host_busy_waits_and_retries_without_terminal_failure \
  tests/test_api.py::test_public_callback_message_redacts_glasshive_ids \
  tests/test_profile_runtime.py::test_host_cli_runtime_allows_one_active_worker_per_family -q
```

Result: `3 passed`.

```text
cd viventium_v0_4/GlassHive/runtime_phase1
uv run pytest -q -ra
```

Result: passed; only the expected live CLI/OpenClaw tests were skipped.

```text
uv run --with pytest --with fastmcp --with starlette --with croniter \
  pytest tests/release/test_scheduled_glasshive_prompts.py -q
```

Result: `14 passed, 1 warning`.

```text
git diff --check
git -C viventium_v0_4/GlassHive diff --check
git -C viventium_v0_4/LibreChat diff --check
```

Result: all clean.

## Status Updates

- `SCHED-002`: `PASS` for the real-account built-in Workbench nightly manual proof.
- `PW-029`: `PASS` for real Workbench UI/API scheduled GlassHive prompt delivery.
- `SCHED-006`: `PASS` for completed real-account callback-to-parent-ledger parity; source
  regressions cover capacity-wait and callback ordering.
- `SCHED-007`: remains `PASS` from stale-cache source and synthetic active-runtime proof.
- `SCHED-005`: `PARTIAL`; retry/backoff behavior is fixed and tested, but a live overlapping
  host-worker stress run still needs to prove the visible capacity-wait path on the real runtime.

## Remaining Risk

The automation is reliable for the real built-in nightly delivery path exercised here. The remaining
risk is specifically the live contention case: start one host-native Codex worker, trigger a second
Workbench/GlassHive schedule while the first is active, and verify the second remains queued/retryable
and later completes without terminal `host_worker_busy`.
