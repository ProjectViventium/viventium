# Background Agents QA Report

## Date

- 2026-04-05

## Build Under Test

- Parent repo base commit: `dcabc27`
- Nested LibreChat repo base commit: `1fcacfb2`
- Working tree included changes to:
  - Anthropic endpoint/runtime compatibility
  - background-cortex execution guard
  - built-in source-of-truth background-agent config
  - background-agent docs and QA artifacts

## Steps Executed

1. Targeted Anthropic endpoint and memory regression suite:
   - `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/endpoints/anthropic/llm.spec.ts src/agents/memory.spec.ts`
2. Targeted background-cortex execution regression suite:
   - `cd viventium_v0_4/LibreChat/api && npx jest --runInBand test/services/viventium/backgroundCortexService.test.js`
3. Source-of-truth audit for shipped Anthropic background agents:
   - parsed `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
   - asserted zero background agents still combine `temperature` with implicit Anthropic thinking
4. Install/start-path ownership check:
   - inspected `viventium_v0_4/viventium-librechat-start.sh`
   - verified `detect_viventium_agents_bundle`
   - verified `ensure_viventium_agents_seeded`
   - verified the startup path still prefers `viventium/source_of_truth/local.viventium-agents.yaml`
5. Dry-run built-in agent reseed:
   - `cd viventium_v0_4/LibreChat && node scripts/viventium-seed-agents.js --bundle=viventium/source_of_truth/local.viventium-agents.yaml --dry-run --public`
   - confirmed the corrected source bundle would repair `model_parameters` for:
     - `agent_viventium_confirmation_bias_95aeb3`
     - `agent_viventium_emotional_resonance_95aeb3`
6. Live rollout verification:
   - `cd viventium_v0_4/LibreChat/packages/api && npm run build`
   - rebuilt `packages/api/dist/index.js` with the Anthropic thinking/temperature guard now present in the runtime bundle
   - `cd viventium_v0_4/LibreChat && node scripts/viventium-seed-agents.js --bundle=viventium/source_of_truth/local.viventium-agents.yaml --public`
   - updated the live Mongo agent documents so:
     - `agent_viventium_confirmation_bias_95aeb3` now has `model_parameters.thinking: false`
     - `agent_viventium_emotional_resonance_95aeb3` now has `model_parameters.thinking: false`
   - restarted the local LibreChat backend worker and verified it was listening again on `http://localhost:3180`
7. Review-only second opinion:
   - attempted local `claude -p` review-only pass with explicit timeout
   - helper did not return usable findings before timing out

## Evidence

### Automated Results

- `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/endpoints/anthropic/llm.spec.ts src/agents/memory.spec.ts`
  - `2 passed, 104 tests passed`
- `cd viventium_v0_4/LibreChat/api && npx jest --runInBand test/services/viventium/backgroundCortexService.test.js`
  - `1 passed, 29 tests passed`

### Source-of-Truth Audit

- Result:

```text
{'anthropic_temp_without_explicit_thinking': [], 'count': 0}
```

### Install/Start Ownership Evidence

- `rg -n "detect_viventium_agents_bundle|ensure_viventium_agents_seeded|viventium-seed-agents\\.js|local\\.viventium-agents\\.yaml" viventium_v0_4/viventium-librechat-start.sh`
  - confirmed source-of-truth bundle detection
  - confirmed startup seeding via `viventium-seed-agents.js`
  - confirmed the startup path still points at `viventium/source_of_truth/local.viventium-agents.yaml`

### Dry-Run Reseed Evidence

- `cd viventium_v0_4/LibreChat && node scripts/viventium-seed-agents.js --bundle=viventium/source_of_truth/local.viventium-agents.yaml --dry-run --public`
  - exited successfully
  - reported `runtimeRepair.repaired: true` for:
    - `agent_viventium_confirmation_bias_95aeb3`
    - `agent_viventium_emotional_resonance_95aeb3`
  - this verifies existing local installs would pick up the built-in `thinking: false` correction on
    the normal startup reseed path without hand-editing Mongo

### Live Rollout Evidence

- `cd viventium_v0_4/LibreChat/packages/api && npm run build`
  - completed successfully and refreshed `packages/api/dist/index.js`
  - the built runtime bundle now contains:
    - `hasActiveAnthropicThinking`
    - `sanitizeAnthropicTemperatureForThinking`
- `cd viventium_v0_4/LibreChat && node scripts/viventium-seed-agents.js --bundle=viventium/source_of_truth/local.viventium-agents.yaml --public`
  - completed successfully
  - live Mongo verification confirmed:
    - `agent_viventium_confirmation_bias_95aeb3` has `model_parameters.thinking: false`
    - `agent_viventium_emotional_resonance_95aeb3` has `model_parameters.thinking: false`
- backend runtime verification:
  - restarted the backend worker under nodemon
  - verified a fresh `api/server/index.js` process was running
  - verified `http://localhost:3180` was listening again after restart

### Second Opinion Attempt

- Local `claude -p` review-only pass:
  - timed out without returning substantive output
  - no second-opinion findings were available to incorporate

## Findings

- No blocking regressions found in the focused Anthropic background-agent path.
- The failure mode is now covered at:
  - Anthropic config generation
  - memory-agent execution
  - background-cortex execution after initialization
  - generic user-created Anthropic cortex execution after initialization
  - source-of-truth bundle validation for shipped Anthropic cortices
- The local running stack now has the rebuilt package bundle, live built-in agent reseed, and a
  restarted backend process, so the Anthropic fix is not only present on disk but loaded in the
  active local runtime.

## Residual Risks

- User-created Anthropic agents outside the shipped built-in bundle can still choose combinations
  that depend on Anthropic provider semantics changing again in the future; the runtime guard now
  fails safe by stripping `temperature` whenever active thinking is present.
- Full end-to-end UI verification against a running stack was not performed in this pass because the
  targeted regression suites already exercised the exact failing runtime path.
