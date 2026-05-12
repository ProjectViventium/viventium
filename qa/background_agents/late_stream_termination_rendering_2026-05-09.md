# Late Stream Termination Rendering QA - 2026-05-09

## Scope

Regression coverage for assistant messages that contain visible text plus a late provider/socket
termination error part. This was observed as a usable answer followed by a red "Something went
wrong ... terminated" card in the same assistant message.

## Requirement

- A late stream termination after visible assistant text must not append a generic fatal error card
  to the same message.
- Existing historical messages with `text + terminated error` content parts should render the text
  and structured cortex parts without showing the terminated error card.
- Error-only messages must still show the error.
- Non-termination provider failures after partial text must still show the error so real failures are
  not hidden.

## RCA

The backend catch path in `api/server/controllers/agents/client.js` appended
`ContentTypes.ERROR` for every non-controller-aborted exception. If the provider stream terminated
after text had already been accumulated, the saved assistant message could contain both:

- a visible `text` content part
- an `error` content part with a termination message
- optional cortex status/insight parts

The frontend renderer then rendered all parts in order, so users saw the useful answer and a fatal
error card together.

## Fix

- Backend suppresses only late stream-termination/abort error content parts when visible assistant
  text already exists.
- Backend still creates visible error parts for error-only turns and non-termination provider
  failures.
- Frontend defensively filters historical `text + late termination error` messages at render time.
- Fallback retry policy now treats `text.value` content parts as visible text, matching the runtime
  content shapes seen in stored messages.

## Evidence

Local DB scan, public-safe summary:

- `876` messages with at least one error content part.
- `21` messages with both visible text and an error part.
- The reported failure matched the `text + error: terminated + cortex_insight` shape.

No owner/private conversation rows were modified. Browser QA used a temporary synthetic conversation
for the local QA user and removed it after verification.

## Automated Tests

| Check | Result |
| --- | --- |
| `node --check api/server/controllers/agents/client.js` | Pass |
| `node --check api/server/services/viventium/agentLlmFallback.js` | Pass |
| `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/services/viventium/__tests__/agentLlmFallback.spec.js --runInBand` | Pass, 12 tests |
| `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/controllers/agents/client.test.js --runInBand` | Pass, 99 tests |
| `cd viventium_v0_4/LibreChat/client && npm run test:ci -- src/components/Chat/Messages/Content/__tests__/contentParts.test.ts --runInBand` | Pass, 24 tests |
| `cd viventium_v0_4/LibreChat && npm run test:client` | Pass, 116 suites, 1290 tests |
| `cd viventium_v0_4/LibreChat && npm run test:api` | Pass, 171 suites passed, 2 skipped; 2903 tests passed, 19 skipped |
| `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/test_background_agent_governance_contract.py tests/release/test_productivity_activation_source_of_truth.py -q` | Pass, 28 tests |

## ClaudeViv Review

Review-only ClaudeViv pass confirmed the RCA and the two-layer fix direction: suppress the backend
mutation for late terminations after visible text, and tolerate historical rows in the renderer.

Findings addressed after review:

- Added direct catch-path mutation tests, not just helper tests.
- Widened backend and frontend late-termination matching to cover `TypeError: terminated`,
  `AbortError`, and common request/stream abort wording.
- Added frontend coverage proving runtime-hold `{NTA}` rows do not hide a real termination-only
  error.

Scope note: separate GlassHive delegate-row rendering changes and Phase B fallback-persistence work
are covered by their own tests; this report only signs off the same-message `text + terminated
error` failure class.

## Browser QA

Tooling: Playwright CLI against the local LibreChat client, using a synthetic local QA account.

Synthetic content shape:

- user message: synthetic QA prompt
- assistant content parts:
  - `text`: "QA visible answer should remain."
  - `error`: "An error occurred while processing the request: terminated"
  - `cortex_insight`: complete background insight

Observed result:

- Page rendered the user prompt.
- Page rendered the assistant text.
- Page rendered the named background-agent cortex row with the current `Background agent:
  <cortex name>` / `Result from <cortex name>` card wording.
- DOM scan found `0` visible `Something went wrong` / `terminated` error cards.
- The synthetic QA conversation was deleted from local Mongo after the browser verification.

## Result

The reported UI class is covered at both the persistence source and the rendering tolerance layer.
Late stream termination after visible text no longer creates or displays a fatal same-message error
card, while honest error-only and non-termination failures remain visible.
