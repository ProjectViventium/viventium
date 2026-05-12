# Background Cortex Visible Cards Recovery QA - 2026-05-09

## Scope

Regression coverage for a local browser-visible failure where background cortices did not appear
for a decision-analysis prompt, then a follow-up prompt showed cards but the main answer still asked
whether to start background work that was already requested.

This report uses public-safe synthetic prompts and local-only message identifiers. It does not
include credentials, private screenshots, private chat exports, or private account data.

## Root Cause

Primary failure:

- Fast Phase A activation could return zero activated cortices when the primary activation provider
  was degraded and fallback activation did not complete inside the fast budget.
- With zero activation decisions, the runtime emitted no background-cortex card events and persisted
  no structured `cortex_insight` parts. The browser therefore had no cards to render.

Secondary user-visible failure caught by real browser QA:

- After late background work was restored, the main answer could still ask whether to "spin up"
  background work, even though the user had already requested visible background analysis and the
  runtime had started the cards.
- Source prompt updates alone were not enough because live/client-sent agent instructions can lag
  source-of-truth prompt changes. The runtime now carries a narrow background-card contract guard.

Rejected fix shape:

- No runtime keyword or regex intent classifier was added for user intent. Activation remains owned
  by activation prompts/config. The runtime changes handle provider degradation and card lifecycle.

## Fix Summary

- Added temporary activation-provider health suppression so retryable provider/auth/network failures
  do not consume every activation attempt before a configured fallback can run.
- Added late non-blocking Phase A/B recovery when fast Phase A returns zero activations from timeout
  or provider degradation. The first answer remains fast; late cards attach to the same message.
- Added a runtime-owned background-card instruction guard so stale live instructions do not cause the
  main answer to deny, explain away, or offer to start already requested background cards.
- Updated `main.background_cortices` source prompt with the same card/activation contract.
- Promoted the incident into ACT-18 and ACT-19 in the background-agent eval bank and coverage matrix.
- Added/updated focused tests for provider degradation, terminal structured card persistence, and the
  main-agent card contract.
- Fixed two additional card-rendering gaps found during independent review:
  - terminal silent/no-response cortex completions with only a preserved activation reason no longer
    render as empty "Additional thought" rows
  - terminal cortex error parts now pass and render their error detail in the expanded card
- Applied ClaudeViv follow-up hardening:
  - late Phase B now passes `res: null` instead of a possibly closed main HTTP response
  - runtime card guard injection is covered for idempotency/no-op behavior
  - late activation timeout parsing/clamping is covered
  - activation-provider health suppression TTL expiry is covered
  - source prompt/runtime guard drift is pinned by the release contract

## Browser QA Evidence

### Pass 1: Restored Cards

Prompt shape:

- User asked for confirmation-bias review, red-team analysis, fast answer first, and visible
  background analysis.

Observed:

- Browser showed six named background cards:
  - Background Analysis
  - Confirmation Bias
  - Red Team
  - Pattern Recognition
  - Emotional Resonance
  - Strategic Planning
- Message content persisted as `text + 6 cortex_insight`.
- `brewingCount=0`.
- All six structured cortex parts had `status=complete`, `hasInsight=true`, and no error.
- Expanded Red Team showed:
  - Why this ran
  - confidence
  - Result from Red Team
  - Background agent: Red Team
  - Analysis complete

Gap found:

- The main answer still offered to start deeper background work. This triggered ACT-19 and the
  stronger runtime/source guard.

### Pass 2: Corrected Main Answer + Cards

Prompt shape:

- Synthetic vendor-partnership bias/red-team prompt asking for fastest useful answer first and
  visible background analysis.

Observed in browser:

- First response gave a substantive answer immediately.
- Six named background cards rendered above the main answer.
- Expanded Red Team card showed Why/Confidence/Result/Footer/Analysis complete.
- A later follow-up message was generated after all background insights finished.

Observed in DB/logs:

- Late Phase A activated `6/11` cortices through fallback activation.
- Phase B completed `6/6 visible insights, 0 silent completions, 0 errors`.
- Parent assistant message persisted as `text + 6 cortex_insight`.
- `brewingCount=0`.
- `textHasForbidden=false` for:
  - offering to spin up/start/run background work
  - claiming card/UI control problems
  - saying there is nothing to show

## Automated Verification

Commands run:

```bash
node --check viventium_v0_4/LibreChat/api/server/controllers/agents/client.js
node --check viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js
PYTHONPATH=. uvx --with pytest --with pyyaml pytest tests/release/test_background_agent_governance_contract.py -q
cd viventium_v0_4/LibreChat && npm run test:api -- --runInBand api/server/controllers/agents/client.test.js api/server/services/__tests__/BackgroundCortexService.activationPolicy.spec.js
cd viventium_v0_4/LibreChat && npm run test:client -- --runInBand src/components/Chat/Messages/Content/__tests__/Part.cortex.test.tsx src/components/Chat/Messages/Content/__tests__/ProgressText.cortex.test.tsx
python3 scripts/viventium/prompt_registry.py --json-out "<app-support>/runtime/prompt-bundle.json"
python3 scripts/viventium/config_compiler.py --check-prompt-drift --compare-reviewed
git diff --check
git -C viventium_v0_4/LibreChat diff --check
```

Results:

- JS syntax checks passed.
- Background-agent governance contract: `17 passed`.
- Background controller + activation-policy Jest suites: `125 passed`.
- Cortex frontend card rendering: `2` targeted suites, `10 passed`.
- Prompt-bundle drift gate: `drift_count=0`, `prompt_count=61`.
- Whitespace diff checks passed for parent and nested LibreChat repos.

## ClaudeViv Review

ClaudeViv agreed the RCA and fix shape are coherent and aligned with the no-runtime-keyword-intent
rule. It could not independently verify private local DB/log evidence, but it confirmed the code
paths match the described failure mode.

Material findings addressed in this pass:

- late Phase B should avoid binding to a possibly closed response stream
- runtime guard, timeout clamp, provider-health expiry, and guard drift needed automated coverage

Remaining recommended follow-up:

- automate ACT-18 and ACT-19 as full scripted browser regressions, not only manual browser QA plus
  source/eval-bank contract tests

## Remaining Operational Notes

- The local provider configuration still contains degraded provider paths. The product fix now
  degrades through configured fallbacks instead of silently losing all background work, but the
  underlying provider access/scope issue should still be cleaned up separately.
- Browser QA must remain part of acceptance for this flow. A DB-only pass would have missed the
  main-answer wording issue that appeared after card recovery.
- The final browser tab also logged `api/mcp/connection/status` errors unrelated to the background
  cortex card lifecycle. Card rendering and DB persistence passed, but MCP status health remains a
  separate browser-console cleanup item.
