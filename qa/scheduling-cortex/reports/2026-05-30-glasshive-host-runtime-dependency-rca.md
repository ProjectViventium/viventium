<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 GlassHive Host Runtime Dependency RCA

## Verdict

PASS for the May 30 failure class: the Workbench/GlassHive run failed before `/assign` because
host-native `codex-cli` could not find the Codex binary in the launched service environment, and
Scheduling Cortex collapsed GlassHive's structured 409 body into a generic `HTTP 409: Conflict`.

PASS for the full follow-up contract after the same-day repair run: a safe manual Workbench run
queued through GlassHive, completed, updated the parent ledger, and was visible in Workbench. See
the follow-up report for the private-runtime delivery proof.

## Root Cause

The failure was not generic GlassHive capacity/backpressure. The lost structured body classified the
blocker as `runtime_dependency_missing` with `failure_retryable=0`.

The chain was:

1. Generated runtime/preflight checked `codex` using the interactive shell `PATH`.
2. The launched GlassHive service environment did not have that app-bundled Codex path on `PATH` and
   had no compiled `WPR_CODEX_BIN`.
3. GlassHive correctly refused host `codex-cli` before creating/resuming a worker.
4. Scheduling Cortex discarded `failure_class`, `detail`, and `failure_retryable`, so the run ledger
   recorded only a generic `HttpJsonError`.
5. A separate reliability gap allowed direct GlassHive startup to fall back to repo-local
   `runtime_phase1.db` if `WPR_DB_PATH` was missing from compiled env.
6. The first repair still needed the same safe substrate-recovery rule on the Scheduler REST path:
   if host preflight fails before assignment and there is no host-specific workspace-root
   constraint, retry through sandbox/workstation execution before terminal failure.
7. Follow-up QA found a separate terminal-ledger race: a host run could have a valid final report
   in output while reconcile saw the worker process gone before the exit marker was present. That
   path needed to collect completed output before classifying the run as orphaned.

## Fix

- Config compiler now resolves host CLI paths structurally and emits:
  - `WPR_CODEX_BIN` for the supported app-bundled Codex CLI when shell `PATH` is insufficient.
  - `WPR_CLAUDE_CODE_BIN` / `WPR_OPENCLAW_BIN` when discovered/configured.
  - local `WPR_DB_PATH` for local GlassHive.
- Preflight uses the same Codex app-bundle fallback instead of shell `PATH` only; discovery covers
  `/Applications`, `~/Applications`, and `VIVENTIUM_CODEX_APP_DIRS`.
- GlassHive runtime env loader accepts the host CLI binary env keys.
- Scheduling Cortex preserves structured HTTP JSON failures and records `failure_class` into
  `scheduled_prompt_runs.error_class`.
- Scheduling Cortex retries safe Workbench scheduled dispatches through docker/sandbox execution
  when host `runtime_dependency_missing` occurs before assignment and no host workspace root is
  required.
- GlassHive reconcile collects completed output before orphaning a missing-process or paused-worker
  active run, and emits a `run.interrupted` callback only for true interrupted runs.
- GlassHive reconcile now isolates failures per worker and uses state-checked terminal finalization
  before emitting recovered terminal callbacks.
- Requirements docs and `SCHED-008` now capture the escaped bug.

## Evidence Checked

- Scheduler DB: latest failed Workbench run had no worker/run id and failed at
  `workers/find-or-resume`.
- GlassHive log: project lookup succeeded, `find-or-resume` returned 409, no `/assign` followed.
- Structured probe: `runtime_dependency_missing`, non-retryable, no worker rows.
- Generated env after compile: GlassHive enabled, host workers enabled, Codex host CLI available,
  `WPR_CODEX_BIN=<app-bundled-codex>`, `WPR_DB_PATH=<app-support-glasshive-db>`.
- Live GlassHive health: OK.
- DB alignment: API project count matched App Support DB count and differed from repo-local DB
  count.
- Live no-run host preflight: synthetic `codex-cli` host worker accepted as `paused`; run count was
  `0`.
- Same-day follow-up: the built-in Workbench schedule completed through GlassHive on the real local
  admin account; Scheduler run row, parent ledger, GlassHive DB row, and browser-visible Workbench
  recent-run status agreed. Raw prompt/result/account values were not published.
- Reconcile race proof: the final post-fix run reached `completed` in Scheduler and GlassHive, had
  output present, and delivered queued/started/completed callbacks. A prior QA-created interrupted
  row was terminal and no longer left Workbench in stale `running`.

## Tests

- Focused release regressions: 18 passed after the follow-up recovery and discovery coverage.
- GlassHive runtime/profile/reconcile regressions: 8 passed.
- Full config compiler suite: 108 passed.
- Full preflight suite: 63 passed.
- QA-results public-safety regression: 1 passed after sanitizing pre-existing local artifacts.
- `git diff --check`: PASS.

## ClaudeViv Review

Claude review-only follow-up returned `accept_with_risks`. Actionable risks were incorporated:

- Codex.app discovery now covers the per-user app root and an override, not only `/Applications`.
- Scheduler REST dispatch now has a safe docker recovery branch for host runtime dependency
  blockers without a host workspace-root constraint.
- Launcher idempotence now checks enabled MCP/Telegram sidecars in addition to RAG/search sidecars.

## Remaining Gaps

- `SCHED-005` retryable `host_worker_busy` overlap stress remains separate and still needs a live
  overlapping host-worker proof.
- User-facing transcript recall chat QA remains separate from this scheduler/GlassHive repair.
- The exact missing-process-with-completed-output race is covered by focused regression and normal
  post-fix live delivery, but was not intentionally reproduced on the live runtime after the fix.
