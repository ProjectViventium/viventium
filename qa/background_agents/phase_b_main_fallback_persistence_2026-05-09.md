# Phase B Main-Fallback Persistence QA - 2026-05-09

## Scope

Regression coverage for background Phase B cortices when the primary main model fails before visible
assistant text and `AgentClient.sendCompletion` retries the configured fallback model.

## Requirement

- Phase A activation should run once for the original user turn.
- Phase B execution should keep running even if the primary main model fails before text.
- Fallback `chatCompletion` must not clear the request-wide Phase B promise or start duplicate
  background cortices.
- Durable DB persistence and follow-up adjudication must use the final primary-or-fallback answer.
- Terminal Phase B outcomes must persist as structured content parts on the originating assistant
  message, including visible insights, silent `{NTA}` successes, and terminal errors.

## Code Paths Under Test

- `api/server/controllers/agents/client.js`
  - `sendCompletion`
  - `attachBackgroundCortexCompletionPipeline`
  - sync and async Phase A/B call sites
- `api/server/controllers/agents/client.test.js`
  - `AgentClient Phase B persistence across main-model fallback`

## Automated Tests

Run from `viventium_v0_4/LibreChat` or the repository root as shown.

| Check | Result |
| --- | --- |
| `node --check api/server/controllers/agents/client.js` | Pass |
| `cd api && npm run test:ci -- server/controllers/agents/client.test.js` | Pass, 82 tests |
| `cd api && npm run test:ci -- server/controllers/agents/client.test.js server/services/viventium/__tests__/agentLlmFallback.spec.js server/services/__tests__/BackgroundCortexService.activationPolicy.spec.js server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js server/services/viventium/__tests__/staleCortexMessageRecovery.spec.js server/services/viventium/__tests__/brewingHold.spec.js` | Pass, 166 tests |
| `cd api && npm run test:ci -- server/services/viventium/__tests__/CallSessionService.spec.js` | Pass, 14 tests |
| `npm run test:api` | Pass, 171 suites passed, 2 skipped; 2885 tests passed, 19 skipped |
| `PYTHONPATH=. uvx --with pyyaml pytest tests/release/test_background_agent_governance_contract.py tests/release/test_productivity_activation_source_of_truth.py -q` | Pass, 28 tests |

## Live Browser QA

Tooling: Playwright CLI against the local LibreChat client.

Synthetic prompt:

> QA_PHASEB_FALLBACK_20260509_1904: I am evaluating whether to accept a risky partnership. Please analyze strategic risks, confirmation bias, red-team concerns, and practical next steps. Keep it concise.

Observed runtime evidence:

- Primary main model attempted `anthropic / claude-opus-4-7`.
- Primary failed before assistant text with provider authentication failure.
- Runtime retried fallback `openAI / gpt-5.4`.
- Fallback main turn returned visible assistant text.
- Phase A activated 8 of 11 cortices for the original user turn.
- Phase B completed with 5 visible insights, 3 silent completions, and 0 errors.
- The originating assistant message persisted 8 terminal `cortex_insight` parts:
  - 5 complete visible insights
  - 3 complete silent/no-response successes
- Follow-up adjudication selected `{NTA}`, so no redundant follow-up message was persisted.
- Browser refresh showed named terminal background-agent rows/cards with the current
  `Background agent: <cortex name>` / `Result from <cortex name>` wording instead of stale progress
  labels.

## Result

The main-model fallback path now preserves the original Phase B execution and persists its terminal
structured results on the originating assistant message. No duplicate Phase B pipeline was observed
or produced by the automated one-pipeline test.
