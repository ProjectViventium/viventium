# Phase A / Phase B Background-Agent Reliability QA

## Scope

Verify that background agents behave as a generic nonblocking cognitive layer across direct main
agent tools and supplemental Phase B execution.

This QA covers:

- activation awareness delivered to the main agent
- direct Phase A tool execution when the main agent owns the activated scope
- supplemental Phase B background execution
- terminal UI/persistence behavior for visible insight, silent no-response, and error outcomes
- public-safe live-browser validation with a local QA account

## Root Causes Verified

1. Runtime config normalization dropped `config.viventium`, so activation-policy metadata was not
   reliably available where Phase A needed it.
2. Activation classifier providers could return non-JSON prose when JSON mode was not applied,
   causing false activation failures or confusing degradation logs.
3. The hold decision treated same-scope productivity activation too aggressively, so a main agent
   with matching direct tools could be held behind Phase B instead of answering immediately.
4. A background agent that completed with empty output or `{NTA}` could fail to emit a terminal
   completion payload, leaving a stale brewing/progress row.
5. Local full-tunnel VPN routing can make Groq return provider `403` even when the key/config is
   correct. Split tunneling or excluding provider API traffic is the supported local remediation.
6. A scheduler-style Phase A turn could remain visibly `{NTA}` even after Phase B had useful
   background insights, because `{NTA}` was not treated as an internal no-visible-answer marker
   for forcing a separate Phase B follow-up.
7. Parietal Cortex shipped and live-synced `temperature: 1` on an `openAI / gpt-5.4` execution bag;
   the provider rejected the Phase B run with HTTP 400 before the cortex could produce an insight.
   The body-less 400 does not prove the exact rejected field, but the shipped sampling parameter
   was a real provider-compatibility defect and was removed.

## Product Fixes Under Test

- Preserve `config.viventium` through app config normalization.
- Pass activated-agent descriptions, activation scopes, direct-action surfaces, and direct-action
  coverage into main-agent activation awareness.
- Use strict JSON-only activation prompts and provider JSON mode where supported.
- Allow same-scope supplemental Phase B when the source-of-truth scope explicitly declares it.
- Defer the main response only when an activated direct-action scope has no matching main-agent
  direct-action owner.
- Structurally suppress same-scope background activation after classifier output unless the matching
  direct-action surface explicitly allows supplemental Phase B.
- Emit terminal `cortex_insight` payloads for every Phase B outcome:
  visible insight, silent no-response success, and error.
- Hide silent no-response completions in the UI while still replacing the prior brewing row.
- Log visible insight counts, silent completion counts, and error counts separately.
- Derive stale startup recovery from Phase B execution timeout plus grace.
- Preserve activation reason/confidence/description when brewing rows are replaced by terminal rows.
- Use classed deferred fallback text for provider access, credentials, rate limit, timeout, and
  runtime-restart recovery when the class is known.
- Force a separate Phase B assistant follow-up when the Phase A response is exactly `{NTA}` and
  Phase B has useful output. Phase B must not replace or overwrite Phase A.
- Hide web rendering of runtime-generated `{NTA}` hold text parts using the structured
  `viventium_runtime_hold` flag, while leaving the stored Phase A message and its cortex parts
  intact.
- Strip OpenAI no-sampling reasoning parameters from background cortex and follow-up runtime
  requests before and after agent initialization. The guard is explicit for the observed
  `gpt-5.4` runtime family and does not blindly classify every dotted `gpt-5.x` model as
  no-sampling.
- Remove Parietal Cortex `temperature` from both tracked source-of-truth and the runtime canonical
  model-parameter map; surgically sync the live user-level Parietal model config.
- Keep the shipped main-agent voice route on `anthropic / claude-haiku-4-5` with
  `thinking: false`, matching the existing voice-call contract.

## Automated Checks

| Check | Result |
| --- | --- |
| `node -c api/server/services/BackgroundCortexService.js` | pass |
| `api npm run test:ci -- --runTestsByPath test/services/viventium/backgroundCortexService.test.js --runInBand` | 36 passed |
| `api npm run test:ci -- --runTestsByPath server/services/__tests__/BackgroundCortexService.activationPolicy.spec.js server/services/Config/app.spec.js server/services/viventium/__tests__/brewingHold.spec.js --runInBand` | 30 passed |
| `api npm run test:ci -- --runTestsByPath server/services/__tests__/BackgroundCortexService.activationPolicy.spec.js server/services/viventium/__tests__/staleCortexMessageRecovery.spec.js server/services/viventium/__tests__/cortexFallbackText.spec.js test/services/viventium/backgroundCortexService.test.js --runInBand` | 63 passed |
| `api npm run test:ci -- --runTestsByPath test/services/viventium/backgroundCortexService.test.js server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js server/services/viventium/__tests__/brewingHold.spec.js --runInBand` | 80 passed |
| `api npm run test:ci -- --runTestsByPath test/services/viventium/backgroundCortexFollowUpService.test.js --runInBand` | 75 passed |
| `api npm run test:ci -- --runTestsByPath test/services/viventium/backgroundCortexService.test.js test/services/viventium/backgroundCortexFollowUpService.test.js server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js server/services/viventium/__tests__/brewingHold.spec.js server/services/viventium/__tests__/openAIReasoningParams.spec.js --runInBand` | 159 passed |
| `api npm run test:ci -- --runTestsByPath server/services/__tests__/BackgroundCortexService.activationPolicy.spec.js --runInBand` | 18 passed |
| `uv run --with pytest --with pyyaml python -m pytest tests/release/test_background_agent_governance_contract.py -q` | 14 passed |
| `client npm run test:ci -- --runTestsByPath src/components/Chat/Messages/Content/__tests__/ProgressText.cortex.test.tsx src/hooks/SSE/__tests__/cortexPendingBuffer.spec.ts --runInBand` | 11 passed |
| `client npm run test:ci -- --runTestsByPath src/components/Chat/Messages/Content/__tests__/contentParts.test.ts src/components/Chat/Messages/Content/__tests__/SearchContent.runtimeHold.test.tsx --runInBand` | 18 passed |
| `LibreChat npm run build:data-provider` | pass |
| `LibreChat npm run build:api` | pass |
| `LibreChat npm run build:client` | pass |
| `LibreChat npm run test:client` | 1278 passed |
| `LibreChat npm run test:packages:data-provider` | 806 passed, 1 skipped |
| `uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py -q` | 69 passed |
| `voice-gateway uv run --with pytest python -m pytest tests -q` | 207 passed |
| `telegram-codex uv run --with pytest python -m pytest -q` | 21 passed |
| `telegram-viventium/TelegramVivBot uv run --with pytest python -m pytest ../tests -q` | 237 passed |

The full parallel API suite reached one infrastructure timeout starting `mongodb-memory-server`.
The failed file passed in isolation with 26 tests, so the observed failure is tracked as test
environment contention rather than a product regression.

## Live Browser QA

Environment:

- local LibreChat web/API stack
- local QA account, refreshed from the owner account using local-only ID remapping so tests do not
  dirty the owner account
- sanitized aggregate-only prompt; no names, subjects, event titles, snippets, or private content
  were recorded in this report

Observed result:

- UI emitted background activation/progress for the matching productivity background agent.
- The main assistant answer streamed without waiting for Phase B.
- Main-agent direct tools executed for the connected productivity scope during Phase A.
- Phase B completed as a background insight, not a stuck progress row.
- Persisted assistant content contained direct tool-call parts plus a terminal `cortex_insight`
  part with `status=complete`.
- No persisted `cortex_brewing` part remained for the validated turn.
- After the Parietal hotfix, live Mongo user-level config for Parietal carries
  `model_parameters: { model: "gpt-5.4" }` with no sampling controls, and the active backend
  process restarted after the code change.
- Follow-up review found that the web UI was still capable of rendering literal `{NTA}` for a
  scheduler-style Phase A parent. Client rendering now filters only runtime-hold no-response text
  parts, not arbitrary assistant text, so Phase B remains append-only and the parent DB message is
  not rewritten.

## Second-Opinion Review

ClaudeViv review confirmed the structural fix direction: Parietal was a runtime/provider failure and
Phase B did execute. A later product-contract correction clarified that the visible `{NTA}` handling
must force a separate Phase B follow-up, not replace Phase A. It also identified two gaps before
acceptance:

- the initial OpenAI guard was broader than upstream for dotted `gpt-5.x` model IDs
- the `{NTA}` Phase B delivery path needed persistence-level coverage, not only pure-function
  coverage

Both gaps were addressed before final acceptance: the OpenAI guard now treats `gpt-5.4` as an
explicit observed no-sampling runtime family instead of every dotted `gpt-5.x`, and the
follow-up service now has a regression test for a persisted `{NTA}` parent with mixed complete/error
Phase B parts saving a new assistant follow-up without editing Phase A.
The web renderer also has regression coverage that a `viventium_runtime_hold` `{NTA}` text part is
hidden while persisted cortex insight parts remain visible.
Final review-only passes from Claude and ClaudeViv reported no blocking findings. Their low-risk
cleanup notes were folded back into the implementation: legacy replacement input no longer forces
Phase B behavior, and OAuth terminal-code fallback matching is bounded to avoid substring
false-positives.

## Acceptance

Pass. The validated behavior matches the product contract:

- Phase A is smart enough to do direct connected-tool work when the main agent owns the scope.
- Phase B remains supplemental and nonblocking.
- Activated background agents expose enough scope/description metadata for the main agent to reason
  about what is delegated.
- Silent no-response output is terminal and non-visible, not stuck progress.
- The fix is generic: it is driven by structured source-of-truth metadata and declared scopes, not
  prompt text, user identity, provider labels, or one-off agent names.
