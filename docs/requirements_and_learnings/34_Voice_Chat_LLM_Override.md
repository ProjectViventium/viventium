# Voice Chat LLM Override

## Overview
Voice calls (LiveKit Playground) can use a different LLM model than text chat. Latency matters for
voice, but a faster route that loses intelligence, recall, relevance, or alignment is a regression.
Users may assign a dedicated voice model only when it meets the same behavioral acceptance gates as
the main route.

## Requirements
1. Agent entity gains `voice_llm_model` (string|null), `voice_llm_provider` (string|null), and a
   separate `voice_llm_model_parameters` bag.
2. Agent Builder UI shows a "Voice Chat Model" button that opens a panel for selecting voice
   provider/model and the same model-parameter controls used by the primary model panel.
3. When both fields are set and all three voice activation conditions are met, the agent's
   model/provider are swapped at runtime before validation and the dedicated voice parameter bag is
   merged over the primary model parameters for that runtime call only.
4. When fields are null/empty, a voice-capable agent's main model/provider are used. Eligibility for
   the existing LiveKit STT -> text LLM -> TTS path is declared by `voice_pipeline_llm`. Native
   speech-to-speech support is separately declared by `native_realtime_voice`. A provider excluded
   from the cascaded pipeline fails visibly and requires an explicit supported Voice Call LLM.
5. Follow-up service (background cortex insights) also uses the voice model during voice calls.
6. Sync scripts include voice fields for YAML import/export.
7. Hidden machine-level voice config must not override or replace the agent-visible Voice Call LLM.
8. The voice parameter bag must not overwrite or persist back into the primary `model_parameters`
   bag. Voice settings are separate authoring state.
9. Modern playground disclosures must resolve the effective assistant route from the actual call
   agent and show the concrete provider/model that will answer the call.
10. Shipped source-of-truth voice routes must seed provider-specific voice parameters explicitly so
    fresh installs and syncs preserve the intended behavior without relying on the primary model
    bag. Source-owned examples and fixtures may use provider-specific routes, but public docs must
    not infer a user's current provider or saved fallback from local state. Every dedicated route
    must pass the same recall/tool-ownership and user-grade voice gates as the main route.
11. Voice model parameters must be normalized to the selected voice provider before the runtime call.
    A provider override must not leak incompatible thinking/reasoning fields from the primary model
    bag into the voice request.
12. The Agent Builder optional-model panel must clear the prior provider's parameter bag on a real
    provider change while leaving initial hydration untouched. A mounted panel may briefly observe
    an empty provider before React Hook Form restores persisted agent values; that empty-to-value
    transition is hydration, not a user provider change. This prevents both an OpenAI Responses
    selection from contaminating a subsequently selected xAI Chat Completions route and a persisted
    route from appearing unset after asynchronous form reset. Because the agent selector remains
    available while an optional-model panel is open, each optional panel must also be scoped to the
    form's agent identity. Loading a different agent resets provider-history state; changing the
    provider within the same agent still clears the old provider's parameters.
13. A capability-backed Voice Call LLM must use an exact declared model and supported effort. Agent
    Builder renders the provider's friendly model label and effort choices, including low effort for
    latency-sensitive GlassHive calls; create/update validation applies the declared default and
    rejects stale or unsupported values.

## Architecture Decision and Primary-Source Research (2026-08-01)

Viventium keeps the cascaded LiveKit route as its universal provider boundary and adds GlassHive to
that route. It does not create a GlassHive-specific audio adapter.

- OpenAI's current voice guidance distinguishes native speech-to-speech for natural low latency
  from a chained voice pipeline for predictable workflows and extension of an existing text agent:
  https://developers.openai.com/api/docs/guides/voice-agents
- Current ChatGPT Voice is powered by GPT-Live for natural turn-taking and interruption, while
  longer Codex work runs in separate tasks whose progress and results return to the voice
  conversation. This validates a fast conversational lane plus a durable worker lane rather than
  forcing every spoken turn through a long harness run:
  https://learn.chatgpt.com/docs/features/voice
- OpenAI's current Work/Codex voice guidance says Voice uses the tools and permissions of the
  selected experience and can coordinate longer agentic tasks. That supports preserving the same
  declared Viventium tool graph across text and LiveKit authoring instead of maintaining a separate,
  capability-poor voice agent:
  https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- LiveKit recommends STT-LLM-TTS for most production agents because it is modular, observable, and
  mature for tools; native realtime is fastest but less provider-portable:
  https://docs.livekit.io/agents/models/pipelines/
- LiveKit's supported portable extension point is an OpenAI-compatible Chat Completions endpoint
  configured by model, base URL, and API key. GlassHive already owns that standard interface:
  https://docs.livekit.io/agents/models/llm/openai-compatible-llms/

The source review also inspected current `livekit/agents`, `livekit/agents-playground`, and
`livekit-examples/agent-starter-react` checkouts. At review time, LiveKit Agents was 1.6.7 while the
validated Viventium runtime remained pinned to 1.5.10. The intervening voice/OpenAI diff is broad,
so upgrading the SDK is deliberately separate from this provider-capability fix. Viventium reuses
its already working Agent Controller bridge, resumable stream, cancellation, transcript, tools,
Feelings, and cortex behavior.

Performance contract:

- Keep the existing lighter Voice Call LLM as the default for fluid conversation.
- Let users explicitly select GlassHive Codex or Claude and choose a supported lower effort when
  workspace/tool intelligence matters more than first-audio latency.
- GlassHive currently publishes safe activity while working and terminal authored assistant text,
  not fabricated incremental answer tokens. Voice must never speak reasoning/activity as though it
  were the answer. First audio therefore waits for terminal authored text on this optional route.
- Do not enable speculative/preemptive generation for a harness execution until cancellation and
  idempotency prove that an unconfirmed user turn cannot start irreversible or duplicate work.

Cancellation contract:

- **End Call** is explicit user intent. The playground sends the opaque call-session ID through its
  server-side proxy; LibreChat matches the exact user and call-session generation job and aborts it
  with `user_cancelled`. That reason must survive Redis pub/sub so the replica actually running the
  provider cancels the native GlassHive request.
- A passive page/network disconnect is not automatically user cancellation. It must never be
  upgraded to `user_cancelled` merely because the media/SSE transport disappeared.
- If the voice gateway posts its normal transport abort after explicit End Call has already started,
  LibreChat acknowledges the existing cancellation instead of racing a second job finalization.
- End Call is single-flight in the UI. Upstream cancellation failure is logged without session,
  stream, provider-error, or secret values; the room still disconnects after the bounded attempt.
- Refresh/reconnect continuity is a separate acceptance claim: absence of native cancellation is
  necessary but does not by itself prove successful stream reattachment and terminal delivery.

Refresh/reconnect contract:

- The playground derives one stable caller identity from the opaque call-session ID and uses it in
  both the LiveKit token and dispatch metadata. A browser reload may reconnect only that identity
  to the existing room and dispatch.
- The LiveKit room retains the original worker during a bounded 60-second participant departure,
  and the worker uses `close_on_disconnect=false`. A second dispatch attempt is rejected by the
  existing per-call lease before a second model or TTS session can start.
- The voice gateway keeps the LibreChat authoring stream alive across passive media detachment. It
  resumes from raw canonical assistant text, computes the missing suffix before speech
  normalization, and buffers terminal speech for the same caller during the reconnect window.
- If the caller does not return during the bounded window, the authored text remains persisted but
  is not played into an empty room. Passive timeout still does not become native harness
  cancellation; only explicit End Call or a real user interruption owns that transition.
- Presence is checked against the exact caller identity. Observer, worker, or unrelated participant
  presence cannot satisfy reconnect delivery.

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
| Telegram always-voice text | false | text | telegram | NO |
| Telegram voice note | false | voice_note | telegram | NO |
| Scheduler | false | scheduled | — | NO |
| Background cortex follow-up (voice) | true | voice_call | voice | YES |

Telegram always-voice means "text-mode answer plus Telegram audio attachment." It intentionally
does not select the Voice Call LLM, voice-call prompt, or voice-call Phase A policy.

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
  - `resolveVoiceModelParameters(agent, voiceModel, voiceProvider)` — overlays voice-only params on
    top of the primary bag for runtime use, then normalizes the result for the selected provider
  - `normalizeVoiceModelParametersForProvider(...)` — strips provider-incompatible thinking fields
    and maps compatibility shapes such as legacy voice `thinking: false` onto the provider's
    supported no-reasoning parameter
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
- **Invalid voice model**: Warning logged and falls back only when the main model is itself
  voice-capable; otherwise the call fails visibly.
- **Provider excluded from the cascaded pipeline**: An absent or invalid Voice Call LLM fails the
  call visibly when the primary provider does not declare `voice_pipeline_llm` (or legacy
  `realtime_voice`) support; falling back to that primary is forbidden.
- **GlassHive main or explicit Voice Call LLM**: Valid because GlassHive declares
  `voice_pipeline_llm: true` and `native_realtime_voice: false`. It is a text author inside the
  existing LiveKit cascade, not a native audio-session model.
- **Legacy machine env voice settings present**: Ignored for Voice Call LLM selection.
- **modelsConfig unavailable**: Voice model trusted from DB (allows cold-start scenarios).
- **Existing agents without voice fields**: UI shows "Using main model" and runtime stays on the
  primary model bag.
- **Voice override cleared after prior tuning**: Clear resets provider/model and stores an empty
  voice parameter bag so stale voice-only settings do not silently persist.
- **Same provider/model with voice-only parameters**: If the Voice Call LLM selects the same
  provider/model as the primary model but carries a non-empty `voice_llm_model_parameters` bag,
  runtime must still apply the voice parameter bag. Same-route voice params are an intentional
  override, not a no-op. This is required for primary Anthropic Opus text chat with
  `thinking: true` while voice uses the same Opus model with `thinking: false`.
- **Anthropic voice `thinking: false`**: For Anthropic, persisted `thinking: false` means "consume
  this UI/DB flag and omit Anthropic thinking from the runtime request." It must not be passed into
  the Agents graph/client options as a literal `false`, because downstream Anthropic/LangGraph
  plumbing can treat a non-null `thinking` key as an active thinking configuration. Runtime must
  remove `thinking`, `thinkingBudget`, `thinkingLevel`, `effort`, and OpenAI/xAI-style
  `reasoning_effort` before constructing the Anthropic voice run.
- **xAI Grok 4.3 no-reasoning voice route**: For xAI Chat Completions, low-latency voice must use
  `reasoning_effort: "none"` in the provider request. In LibreChat's LangChain ChatOpenAI wrapper,
  the xAI Chat Completions route must carry that field through `modelKwargs.reasoning_effort`; a
  plain intermediate `llmConfig.reasoning_effort` can look correct in app logs while failing to
  reach the final provider request for this custom endpoint. As of the 2026-05 xAI docs and live
  API probes, there is no accepted `grok-4.3-non-reasoning` slug; the supported non-reasoning
  route is `grok-4.3` (or its current aliases) with `reasoning_effort: "none"`. Older xAI
  non-reasoning slugs such as `grok-4-1-fast-non-reasoning` and `grok-4.20-non-reasoning` do not
  accept `reasoning_effort` on Chat Completions before provider-side retirement redirects, so the
  adapter must not attach that knob to all xAI model names indiscriminately. Runtime/provider-fetch
  telemetry must verify the actual request shape, not just the voice config object. `thinking:
  false` is an Anthropic-shaped field and must not be sent to xAI. Runtime may map legacy live
  voice params with `thinking: false` to `reasoning_effort: "none"` for compatibility, but the
  durable voice parameter bag should store the xAI-native shape.
- **xAI Responses vs Chat Completions**: xAI Responses uses `reasoning: { effort: "none" }`.
  Viventium's current xAI voice route uses the OpenAI-compatible Chat Completions path, so runtime
  must preserve `reasoning_effort` for the `xai` endpoint unless `useResponsesApi` is explicitly
  true. This is provider-specific request-shape normalization, not a silent model remap.
- **Voice reasoning leak guard**: The Voice Call LLM no-reasoning knob controls the provider
  request, but the voice surface still must be defensive. If any provider emits reasoning deltas in
  voice mode, runtime suppresses them from the resumable stream and from saved assistant content.
  Voice transcripts should contain audible assistant text only; text chat may still show reasoning
  blocks when that mode/provider is intentionally configured.

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
