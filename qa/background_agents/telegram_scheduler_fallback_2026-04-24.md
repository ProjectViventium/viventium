# Scheduled Telegram Fallback QA

## Date

- 2026-04-24

## Scope

Validate the scheduled Telegram path for deferred cortex failures:

- scheduled cortex polling threads `scheduleId` into the LibreChat cortex-state endpoint
- the generic deferred failure sentence is suppressed for scheduled runs
- visible best-effort fallback insight text is recorded as degraded delivery, not ordinary delivery
- scheduler persistence keeps compatible run status while making `last_delivery_outcome` truthful

## Acceptance

- `/api/viventium/scheduler/cortex/:messageId` and `/api/viventium/telegram/cortex/:messageId`
  return `canonicalTextSource` and `canonicalTextFallbackReason`.
- When `scheduleId` is present and no usable insight exists, `canonicalText` is empty and
  `canonicalTextFallbackReason` is `empty_deferred_response`.
- Python scheduler dispatch does not send empty scheduled fallback text to Telegram.
- If fallback insight text is visible, channel and aggregate delivery outcomes are
  `fallback_delivered`.
- Scheduler persistence stores `last_delivery_outcome=fallback_delivered` for visible fallback text,
  while preserving `last_status=success` for a completed degraded run.
- Scheduler persistence also stores deferred fallback degradation metadata when empty scheduled
  fallback text is suppressed.
- Installed-runtime signoff must verify the Anthropic thinking-block sanitizer is present and loaded,
  because fallback classification is only the defensive ledger behavior after a model execution
  failure.

## Causal Chain

- `api/server/services/viventium/cortexFallbackText.js:74` suppresses the generic deferred failure
  sentence only when structured schedule context is present.
- `api/server/services/viventium/cortexMessageState.js:214` returns structured fallback provenance
  for scheduled deferred failures.
- `api/server/routes/viventium/scheduler.js:563` and
  `api/server/routes/viventium/telegram.js:1259` expose the `scheduleId` query parameter to
  cortex-state recovery.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1213` propagates `scheduleId`
  during scheduler polling.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1298` promotes usable fallback
  insight text or preserves the suppressed fallback reason.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1901` and `dispatch.py:2235`
  classify fallback visibility as `fallback_delivered` or `suppressed`, never ordinary
  `sent/delivered`.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py:29` and `scheduler.py:231`
  persist fallback degradation metadata for both visible and suppressed deferred fallback outcomes.

## Evidence

- `python3 -m compileall -q viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex`
  - passed
- `cd viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex && uv run --with pytest pytest -q`
  - `68 passed`
- `cd viventium_v0_4/LibreChat/api && npx jest --runInBand test/services/viventium/cortexMessageState.test.js server/routes/viventium/__tests__/scheduler.spec.js server/routes/viventium/__tests__/telegram.spec.js server/services/viventium/__tests__/anthropicThinkingPatch.spec.js server/services/viventium/__tests__/normalizeTextContentParts.spec.js server/services/viventium/__tests__/sanitizeAggregatedContentParts.spec.js`
  - `6 test suites passed, 70 tests passed`

## Residual

- The installed runtime tree was inspected separately and still used an older LibreChat checkout that
  did not contain `anthropicThinkingPatch.js`. Live rollout was not attempted in this QA pass because
  that installed tree had substantial unrelated local modifications that require explicit
  reconciliation before upgrade/restart.
