<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Nightly Workflow Live Watch

## Scope

Public-safe verification of the repaired Workbench scheduled-prompt path:

`scheduled prompt -> rendered placeholders -> GlassHive host run -> terminal callbacks -> Scheduler
ledger -> Workbench visible state`

This run used the real local runtime and the real local admin account, but this report intentionally
omits the account identifier, raw prompt text, raw callback payloads, private result text, browser
snapshot, local absolute App Support paths, and launch token.

## Requirements

- `docs/requirements_and_learnings/01_Key_Principles.md`: evaluate quality plus performance, keep
  fixes simple, preserve separation of concerns, run full-view QA, and do not treat source changes
  as done without runtime/user-path evidence.
- `qa/README.md`: Scheduler QA must use the product path, visible result, supporting logs/state, and
  public-safe evidence.
- `qa/scheduling-cortex/cases.md`: `SCHED-002`, `SCHED-006`, and `SCHED-009`.
- `qa/prompt-workbench/cases.md`: `PW-029`.

## Before State

- Local timestamp before the watched run: `2026-05-30T17:18:14-0700` (`2026-05-31T00:18:14Z`).
- `bin/viventium status`: Viventium ready. LibreChat frontend/API, Modern Playground, Telegram
  Bridge, Telegram Codex, Conversation Recall, SearXNG, Firecrawl, Google Workspace MCP, Microsoft
  365 MCP, and the macOS helper were running/configured.
- GlassHive callback metrics:
  - `callback_pending`: `0`
  - `callback_delivering`: `0`
  - `callback_dead_lettered`: `2`
  - `callback_max_attempts`: `8985`
  - `callback_oldest_pending_age_seconds`: `0`
- Callback outbox DB status counts:
  - `dead_lettered`: `2`, max attempts `8985`
  - `delivered`: `199`, max attempts `10`
  - no `pending` or `delivering` rows
- The two `dead_lettered` rows were historical rejected callback rows from the previous escaped
  bug. They are now terminal audit records, not an active delivery backlog.
- Sanitized historical classes: one terminal HTTP 403 class and one retry-budget-exhausted class.
- The pre-watch `callback_max_attempts` value was later refined to report active callback rows only;
  see "Claude Review Follow-up" below. The underlying DB counts did not change.
- The built-in Workbench schedule was active, timezone `America/Los_Angeles`, executor
  `glasshive_host`, next due at `2026-05-31T10:00:00Z`, previous last status `success`, and previous
  delivery outcome `sent`.

## Watched Behavior

- Trigger path: Workbench scheduled-prompt manual-run API for the built-in nightly prompt.
- New scheduled-prompt run id present.
- Watch window: `2026-05-31T00:19:00Z` through `2026-05-31T00:20:11Z`.
- Poll behavior:
  - `00:19:00Z`: run `queued`; rendered hash present; variable snapshot hash present; GlassHive run
    id present.
  - `00:19:05Z`: run `running`; rendered hash, variable snapshot hash, and GlassHive run id still
    present.
  - `00:19:10Z` through `00:20:06Z`: run remained `running` with the same required artifacts.
  - `00:20:11Z`: run `completed`.
- Terminal API state:
  - status `completed`
  - executor `glasshive_host`
  - result summary present
  - error class empty
  - GlassHive run id present
  - private detail pointer present
  - rendered hash present
  - variable snapshot hash present

## After State

- Parent scheduler task ledger:
  - last run at `2026-05-31T00:19:00.305388Z`
  - last status `success`
  - last delivery outcome `sent`
  - last delivery at `2026-05-31T00:20:07.535803Z`
  - next run remains `2026-05-31T10:00:00Z`
- Latest `scheduled_prompt_runs` row:
  - scheduled-prompt run prefix present
  - task prefix present
  - status `completed`
  - executor `glasshive_host`
  - rendered hash length `16`
  - variable snapshot hash length `16`
  - GlassHive run prefix present
  - callback payload present
  - private detail pointer present
  - error class empty
- Latest GlassHive run row:
  - run prefix present
  - state `completed`
  - queued at `2026-05-31T00:19:00.3432Z`
  - started at `2026-05-31T00:19:00.3591Z`
  - ended at `2026-05-31T00:20:07.5204Z`
  - output chars `839`
  - error chars `0`
  - retry attempts `0`
- Callback outbox rows for the new run:
  - `worker.resumed_by_alias`: `delivered`, attempts `1`
  - `run.queued`: `delivered`, attempts `1`
  - `run.started`: `delivered`, attempts `1`
  - `run.completed`: `delivered`, attempts `1`
  - last error length `0` for each row
- Final callback metrics after the watched run and follow-up runtime restart:
  - `callback_pending`: `0`
  - `callback_delivering`: `0`
  - `callback_dead_lettered`: `2`
  - `callback_max_attempts`: `0`
  - `callback_oldest_pending_age_seconds`: `0`
- Final callback outbox DB status counts:
  - `dead_lettered`: `2`, max attempts `8985`
  - `delivered`: `203`, max attempts `10`
  - no `pending` or `delivering` rows
- `dead_lettered` delta during the watched run: `0`.

## Browser Evidence

Playwright opened Prompt Workbench through the helper launch token, selected the built-in schedule,
and evaluated the visible DOM without saving a public screenshot. The UI showed:

- Prompt Workbench loaded.
- The built-in scheduled prompt was visible and selectable.
- The schedule detail surface contained GlassHive indicators.
- The selected schedule surface contained completed/sent indicators.
- The detail surface included current date/time markers and no visible failed or delivering callback
  state after expansion.

The temporary Playwright snapshot was deleted after the check because Workbench can display private
prompt and memory text.

## Commands Run

- `curl /v1/metrics/summary` against the local GlassHive runtime: **PASS**, no pending or delivering
  callback rows.
- Sanitized Scheduler SQLite checks for latest task/run rows: **PASS**, parent ledger matched the
  child terminal run.
- Sanitized GlassHive SQLite checks for latest run/callback rows: **PASS**, child run completed and
  all callback events delivered once.
- `bin/viventium status`: **PASS**, runtime ready.
- Playwright CLI Workbench visible check: **PASS**.
- `uv run --with pytest --with pyyaml --with 'pydantic>=2' python -m pytest
  tests/release/test_scheduled_glasshive_prompts.py tests/release/test_qa_results_public_safety.py
  -q`: **13 passed, 5 skipped**.
- GlassHive runtime tests from `viventium_v0_4/GlassHive/runtime_phase1`:
  `uv run --with pytest python -m pytest tests/test_api.py tests/test_profile_runtime.py -q`:
  **188 passed**.
- Follow-up focused callback cluster after Claude review:
  `uv run --with pytest python -m pytest tests/test_api.py -q -k "callback or metrics_include"`:
  **PASS**.
- `python3 -m py_compile` for changed GlassHive service/store/test files: **PASS**.
- Supported runtime restart after the metric/terminal-missing-URL refinement: **PASS**; final
  `bin/viventium status` returned ready and final metrics showed active `callback_max_attempts` `0`.

## Claude Review Follow-up

Claude's first long review returned useful challenges but could not independently read files through
its own tool session, so it was treated as a challenge list, not a ratification. Confirmed findings
addressed here:

- Nightly callback health must be delta-based. The case and report now require a before/after
  `dead_lettered` delta; the watched run delta was `0`.
- `callback_max_attempts` must not be permanently pinned by old terminal audit rows. The live metric
  now reports active `pending`/`delivering` rows only; after restart it was `0` while the historical
  DB audit rows remained intact.
- Missing callback URL is deterministic and now dead-letters immediately instead of consuming a retry
  budget.

A shorter final Claude review then directly inspected the final files and accepted the result:

- implementation is configuration/status-code driven with no user, prompt, or agent-name hacks;
- active-row `callback_max_attempts` is correct and regression-covered;
- the health gate is sufficient only when all required sub-metrics are checked together:
  `dead_lettered` delta, active backlog, active max attempts, oldest pending age, and stale
  `delivering`;
- the report is honest that this proves the manual post-trigger workflow, not the unattended timer
  tick itself.

Remaining risks from Claude: the unattended due tick still needs observation, no permanent callback
fault was injected into the real user runtime, and the nightly health gate is procedural unless a
future automation wrapper enforces all sub-metrics.

## Verdict

PASS for the simple scheduled-prompt workflow exercised here:

- placeholder rendering produced stored hashes;
- GlassHive received and completed the delegated run;
- terminal callbacks reached Scheduling Cortex;
- parent delivery ledger advanced to `success` / `sent`;
- Workbench showed the completed/sent result;
- callback outbox health had no hidden `pending` or `delivering` backlog.
- callback outbox health had no fresh `dead_lettered` delta and active max attempts was `0` after
  the metric refinement.

`SCHED-002`, `SCHED-006`, and `PW-029` are PASS for this manual scheduled run on the real runtime.
`SCHED-009` is PASS for synthetic bounded-termination regressions plus the real run's outbox-health
gate; no permanent callback fault was intentionally injected into the real user runtime.

This is not a claim that the next unattended `03:00` tick has already occurred. The unattended due
tick still needs to be observed after `2026-05-31T10:00:00Z`, but the same product path that the due
tick uses is now proven runnable end to end.

## Public Safety

Excluded from this report: raw scheduled prompt text, rendered prompt text, private result text,
account email, launch token, callback payload JSON, private detail path, private memory contents,
browser snapshot, local absolute runtime paths, and raw logs.
