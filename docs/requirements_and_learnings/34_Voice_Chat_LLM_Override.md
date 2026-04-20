# Voice Chat LLM Override

## Overview
Voice calls (LiveKit Playground) can use a different LLM model than text chat. For voice, latency matters more than reasoning depth — users can assign a faster model (e.g., xAI `grok-4-1-fast`) for voice while keeping a smarter model (e.g., `claude-opus-4-7`) for text.

## Requirements
1. Agent entity gains `voice_llm_model` (string|null), `voice_llm_provider` (string|null), and a
   separate `voice_llm_model_parameters` bag.
2. Agent Builder UI shows a "Voice Chat Model" button that opens a panel for selecting voice
   provider/model and the same model-parameter controls used by the primary model panel.
3. When both fields are set and all three voice activation conditions are met, the agent's
   model/provider are swapped at runtime before validation and the dedicated voice parameter bag is
   merged over the primary model parameters for that runtime call only.
4. When fields are null/empty, the agent's main model/provider are used (fully backward compatible).
5. Follow-up service (background cortex insights) also uses the voice model during voice calls.
6. Sync scripts include voice fields for YAML import/export.
7. Hidden machine-level voice config must not override or replace the agent-visible Voice Call LLM.
8. The voice parameter bag must not overwrite or persist back into the primary `model_parameters`
   bag. Voice settings are separate authoring state.
9. Modern playground disclosures must resolve the effective assistant route from the actual call
   agent and show the concrete provider/model that will answer the call.
10. Shipped source-of-truth for Anthropic voice routes must set `voice_llm_model_parameters.thinking: false`
    explicitly so fresh installs and syncs preserve low-latency voice behavior without relying on
    inheritance from the primary model bag.

## Activation Conditions (all three required)
| Condition | Source | Check |
|-----------|--------|-------|
| Voice mode | `req.body.voiceMode` | `=== true` |
| Input mode | `req.body.viventiumInputMode` | `=== 'voice_call'` |
| Surface | `resolveViventiumSurface(req)` | `=== 'voice'` |

## Cross-Surface Matrix
| Surface | voiceMode | inputMode | surface | Override? |
|---------|-----------|-----------|---------|-----------|
| Web UI text chat | false | — | — | NO |
| LiveKit Playground voice call | true | voice_call | voice | YES |
| Telegram text | false | text | telegram | NO |
| Telegram voice note | false | voice_note | telegram | NO |
| Scheduler | false | scheduled | — | NO |
| Background cortex follow-up (voice) | true | voice_call | voice | YES |

## Architecture

### Data Layer
- **Mongoose schema** (`packages/data-schemas/src/schema/agent.ts`): `voice_llm_model`,
  `voice_llm_provider`, and optional `voice_llm_model_parameters`
- **TypeScript types** (`packages/data-provider/src/types/assistants.ts`,
  `packages/data-schemas/src/types/agent.ts`): voice provider/model plus a dedicated
  `voice_llm_model_parameters?: AgentModelParameters`
- **Zod validation** (`packages/api/src/agents/validation.ts`): voice provider/model plus optional
  `voice_llm_model_parameters`
- **Default form values** (`packages/data-provider/src/schemas.ts`): provider/model default to
  `null`; voice parameter bag is omitted until used or explicitly cleared
- **Seed/sync contract** (`scripts/viventium-seed-agents.js`, `scripts/viventium-sync-agents.js`):
  source-of-truth import/export must preserve `voice_llm_model_parameters` exactly, including
  explicit `thinking: false` defaults for shipped Anthropic voice routes

### UI Layer
- **VoiceLlmPanel.tsx**: Voice provider/model panel plus the shared parameter grid used by
  `ModelPanel.tsx`, but bound to `voice_llm_model_parameters`
- **AgentConfig.tsx**: "Voice Chat Model" button after "Model*" showing voice provider icon + model name, or "Using main model" when empty.
- **AgentPanel.tsx**: Routes `Panel.voiceLlmModel` to VoiceLlmPanel. Includes voice fields and
  aligned voice-model parameters in `composeAgentUpdatePayload()`.
- **Modern playground Wing Mode disclosure**: Resolves the effective assistant route from the
  call-session agent and shows the concrete provider/model plus whether it came from the agent
  Voice Call LLM or inherited the agent primary LLM.

### Runtime Layer
- **voiceLlmOverride.js** (`api/server/services/viventium/`): Encapsulates activation check, validation, fallback, and model swap.
  - `isVoiceCallActive(req)` — checks all three conditions
  - `isVoiceModelValid(model, provider, modelsConfig)` — validates against available models
  - `resolveVoiceOverrideAssignment(agent)` — reads only explicit agent `voice_llm_*` fields
  - `resolveVoiceModelParameters(agent, voiceModel)` — overlays voice-only params on top of the
    primary bag for runtime use
  - `applyVoiceModelOverride(agent, req, modelsConfig)` — mutates the runtime agent in place
- **initialize.js**: Calls `applyVoiceModelOverride()` after agent loaded, before `validateAgentModel()`
- **addedConvo.js**: Same pattern for parallel/handoff agents

### Null Preservation (v1.js)
`removeNullishValues()` strips null values. Voice fields are extracted before that call and re-assigned if `=== null`, same pattern as the `avatar` field. This allows "Clear" in the UI to actually set fields to null in MongoDB.

### Follow-Up Service
`BackgroundCortexFollowUpService.generateFollowUpText()` resolves effective model/provider from
explicit voice fields when `isVoiceCallActive(req)` returns true and reuses the dedicated voice
parameter bag for that spoken follow-up path.

## Edge Cases
- **One field set, other null**: Override skipped (both required). UI enforces linked comboboxes.
- **Invalid voice model**: Warning logged, fallback to main model. Never fails the request.
- **Legacy machine env voice settings present**: Ignored for Voice Call LLM selection.
- **modelsConfig unavailable**: Voice model trusted from DB (allows cold-start scenarios).
- **Existing agents without voice fields**: UI shows "Using main model" and runtime stays on the
  primary model bag.
- **Voice override cleared after prior tuning**: Clear resets provider/model and stores an empty
  voice parameter bag so stale voice-only settings do not silently persist.

## Files Modified
| File | Change |
|------|--------|
| `packages/data-provider/src/types/assistants.ts` | Add voice fields to Agent, AgentCreateParams, AgentUpdateParams |
| `packages/data-schemas/src/schema/agent.ts` | Add Mongoose fields |
| `packages/data-schemas/src/types/agent.ts` | Add to IAgent interface |
| `packages/api/src/agents/validation.ts` | Add Zod validators |
| `packages/data-provider/src/schemas.ts` | Add to defaultAgentFormValues |
| `client/src/common/agents-types.ts` | Add to AgentForm type |
| `client/src/common/types.ts` | Add Panel.voiceLlmModel enum |
| `client/src/components/SidePanel/Agents/VoiceLlmPanel.tsx` | **NEW** — Voice model panel |
| `client/src/components/SidePanel/Agents/ModelParametersSection.tsx` | **NEW** — shared parameter grid for main and voice model panels |
| `client/src/components/SidePanel/Agents/AgentConfig.tsx` | Voice model button |
| `client/src/components/SidePanel/Agents/AgentPanel.tsx` | Panel routing + payload |
| `client/src/locales/en/translation.json` | i18n keys |
| `api/server/controllers/agents/v1.js` | Null preservation |
| `api/server/services/viventium/voiceLlmOverride.js` | **NEW** — Runtime override helper |
| `api/server/services/Endpoints/agents/initialize.js` | Override injection |
| `api/server/services/Endpoints/agents/addedConvo.js` | Override injection |
| `api/server/services/viventium/BackgroundCortexFollowUpService.js` | Voice model resolution |
| `scripts/viventium-sync-agents.js` | AGENT_FIELDS |
| `scripts/viventium-seed-agents.js` | AGENT_FIELDS |

## Added: 2026-02-24
