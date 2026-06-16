<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-10 Fallback Reconnect Error Rendering QA

Status: **PASS** for accurate fallback reconnect wording on LibreChat and Telegram mappings.

## Escaped Symptom

A real turn hit an Anthropic provider rate limit, attempted the configured `openAI / gpt-5.4`
fallback, then failed because the OpenAI connected account needed reconnect. The visible surfaces
collapsed that into generic wording such as `Connection error` or a stale provider-rate-limit
message, leaving out the action: reconnect the OpenAI connected account.

Sanitized DB inspection for 2026-06-10 found four persisted assistant error parts with
`error_class: provider_rate_limited` and the generic provider-rate-limit text. None of those stored
parts contained reconnect guidance, which matches the user-visible failure.

## Fix Summary

- Agent completion errors now classify connected-account reconnect failures as
  `provider_connected_account_reconnect_required` before generic rate-limit/auth classes.
- If a primary provider already emitted a recoverable rate-limit error part and lazy fallback
  initialization then fails because the fallback connected account needs reconnect, the stale primary
  error part is replaced with a composite actionable error:
  primary was rate-limited, fallback could not start, reconnect the fallback provider.
- Sanitized logs now include `action: reconnect_connected_account` and provider name for this class.
- LibreChat error rendering no longer wraps known actionable reconnect text in the generic
  `Something went wrong` wrapper.
- Telegram stream error mapping passes through the same composite reconnect message instead of
  collapsing it to a generic connection error.

## Browser Evidence

Synthetic persisted fixture, loaded through the real local LibreChat browser UI with the configured
runtime test account:

```json
{
  "conversationHash": "fa5e5586c28e",
  "hasActionableBefore": true,
  "hasActionableAfter": true,
  "genericWrapperBefore": false,
  "genericWrapperAfter": false,
  "staleRateLimitBefore": false,
  "staleRateLimitAfter": false
}
```

The QA script cleaned up the synthetic conversation/session after the run. A cropped public-safe
screenshot of only the error bubble was saved under `output/playwright/connected-accounts-handoff/`.

## Automated Checks

PASS:

- `node --check`:
  - `viventium_v0_4/LibreChat/api/server/controllers/agents/client.js`
  - `viventium_v0_4/LibreChat/api/server/services/Endpoints/agents/initialize.js`
  - `viventium_v0_4/LibreChat/api/server/services/viventium/agentLlmFallback.js`
  - `qa/connected-accounts-handoff/scripts/reconnect_error_browser_qa.cjs`
- `npm exec --workspace api -- jest server/controllers/agents/client.test.js --runInBand --coverage=false`
  - Result: 126 passed.
- `npm exec --workspace api -- jest server/services/viventium/__tests__/agentLlmFallback.spec.js --runInBand --coverage=false`
  - Result: 17 passed.
- `cd client && npm exec -- jest src/components/Messages/Content/__tests__/Error.test.tsx --runInBand --coverage=false`
  - Result: 2 passed.
- `uv run --with pytest --with httpx python -m pytest tests/test_librechat_bridge.py::test_stream_error_message_classifies_tool_errors -q`
  - Result: 1 passed.
- `npm run build:client`
  - Result: passed, including post-build verification.
- `VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 node qa/connected-accounts-handoff/scripts/reconnect_error_browser_qa.cjs`
  - Result: passed.

## Remaining Gap

No live Anthropic-rate-limit/provider-reconnect failure was forced against external providers. The
regression uses the persisted final-message shape that LibreChat and Telegram consume, plus unit
coverage for the runtime classification path that produces that shape.
