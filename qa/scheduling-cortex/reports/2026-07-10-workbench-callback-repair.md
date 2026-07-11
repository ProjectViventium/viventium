# 2026-07-10 Workbench Callback Repair
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Summary

Status: **PASS for Prompt Workbench / Scheduling Cortex callback chain after repair**.

The July 10 nightly audit found the built-in Workbench reflection run failed before callback/ledger
completion. Repair focused on the durable callback/evidence defects without publishing raw prompt
text, private memory content, local usernames, secrets, or screenshots.

## Findings

- The scheduled Workbench run initially failed because the worker model route was stale and the
  completion-evidence checker incorrectly treated passive structured memory/context lines as
  required output formats.
- A later proof run completed at the GlassHive layer but its callbacks dead-lettered while the local
  Scheduling Cortex sidecar was restarted against the wrong scheduler DB path.
- The normal launcher exports the scheduler DB path from the runtime state root; the manual sidecar
  restart was corrected to use the same App Support scheduler DB as Workbench.
- GlassHive callback delivery now treats `404` from the known local Scheduling Cortex callback URL as
  retryable, while preserving terminal behavior for unknown external `404` endpoints.

## Fixes

- GlassHive run evidence ignores passive structured context key/value lines unless the key is an
  explicit instruction/output key.
- Scheduled-prompt private scratchpad artifact inventory now includes nested periphery `.md` and
  `.json` artifacts under the private scratchpad root, reported only as sanitized relative paths.
- GlassHive callback outbox now retries transient local scheduler `404` responses for
  `/internal/scheduled-prompts/glasshive-callback`.

## Evidence

- Focused callback tests: `7 passed`.
- GlassHive evidence tests: `95 passed`.
- Fresh live proof:
  - Workbench scheduled run: `<scheduled-run-id>`
  - GlassHive run: `<glasshive-run-id>`
  - GlassHive state: `completed`
  - Scheduler child run: `completed`
  - Parent task ledger: success/sent
  - Callback outbox: `run.queued`, `run.started`, and `run.completed` delivered on first attempt
  - Evidence result: `pass`, no failure or warning reasons
  - Worker model: `gpt-5.5`

## Residual Risk

- Historical callback rows from the repair window remain dead-lettered. They are not pending or
  delivering and did not block the fresh proof run.
- The July 10 memory-hardening LaunchAgent receipt is still missing and remains a separate
  memory-hardening scheduled-run miss, not repaired by this callback fix.
- No browser screenshot was saved because it would risk exposing private scheduled prompt context;
  API and DB evidence were used instead.
