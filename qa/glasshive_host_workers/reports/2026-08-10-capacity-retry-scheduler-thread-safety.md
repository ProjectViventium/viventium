# GlassHive Capacity-Retry Scheduler Thread-Safety QA

**Date:** 2026-08-10

**Case:** [`GHHOST-015`](../cases.md#ghhost-015---bounded-capacity-retry-scheduler)

**Status:** PARTIAL — automated safety gate passed; installed real-capacity recovery pending

## Outcome under review

A temporary host-capacity wait must remain a cheap persisted queue state. Hundreds of future retries
must share one scheduler, stay dormant until due, survive restart, and recover exactly once without
creating one timer/thread per run or destabilizing the host.

## Escaped incident

Three local macOS kernel panic reports correlated GlassHive service instances with approximately
9,400-12,300 threads. Memory and swap were not exhausted, and only a small number of future
`host_worker_busy` retry rows were present.

The confirmed loop crossed two inconsistent queue views:

1. The worker processor used a due-aware queue lookup and correctly found no runnable work.
2. It scheduled a process-local timer for the future deadline.
3. Its finalizer then used a due-unaware queued-row lookup and immediately submitted another
   processor for the same worker.
4. The new processor repeated the timer plus immediate-resubmission cycle.

This explains how a few persisted waits produced thousands of threads. The evidence does not support
ordinary memory pressure or browser/voice activity as the root cause.

## Implemented invariant inspected

- `retry_after` in SQLite is the sole capacity-retry clock.
- The per-retry `threading.Timer` path is removed.
- The existing single scheduler processes scheduled runs and due worker retries as independent,
  error-contained phases.
- A newly persisted retry wakes that scheduler; its next wait is bounded by the normal interval or
  the nearest eligible future deadline.
- Worker finalization immediately resubmits only when due-aware queue inspection finds runnable work.
- Due-worker discovery excludes paused and terminated workers before its limit.
- Active-processor ownership deduplicates local dispatch; transactional run claim preserves one
  execution per run.
- Shutdown prevents new retry dispatch, wakes the scheduler, and joins it.
- Persisted deadlines are rediscovered after service restart.

This is a structural scheduler correction. It adds no agent-name, prompt-text, provider-label,
user-identity, or magic response-time routing rule.

## Evidence run

Focused `runtime_phase1/tests/test_api.py` selection: **PASS, 12/12**.

- retryable host-busy wait and eventual completion
- future retry creates neither immediate processor restart nor timer request
- shared scheduler dispatches each due worker once and leaves future work dormant
- persisted retry recovers after service restart
- 200 persisted future retries keep thread count constant instead of creating retry threads
- just-crossed deadline is rechecked promptly
- paused/terminated workers are excluded before discovery limits
- no dispatch begins after shutdown
- one scheduler phase error does not suppress the other
- deadline-lookup failure is logged and falls back to the normal interval
- shutdown during a scheduler cycle terminates the scheduler thread
- capacity retries retain their configured maximum-attempt boundary

A post-fix full `runtime_phase1/tests/test_api.py` run passed 175/175. The post-fix full runtime
suite also passed: 786 passed and five expected skips (791 collected before the stress-only test was
added; the current suite collects 792 cases).

## Still required before completion

- Advance/release capacity and prove every eligible run executes exactly once from SQLite run/event
  counts and terminal callbacks.
- Restart the real affected runtime artifact and repeat the future-wait/recovery path.
- Confirm the installed/running artifact matches the corrected source.

Until the installed real-capacity checks pass, this incident remains `PARTIAL`; no release-readiness
claim is made.

## Public-safety review

This report contains no local paths, process IDs, account or conversation identifiers, raw panic
files, private logs, credentials, prompts, or machine identity. Raw incident evidence remains outside
the public repository.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
