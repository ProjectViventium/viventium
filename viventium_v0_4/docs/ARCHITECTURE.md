<!-- === VIVENTIUM START ===
Document: Architecture and Code Map
Added: 2026-01-09
=== VIVENTIUM END === -->

# Architecture and Code Map

This document maps the live system to code and data structures.

## Component Overview
```
User → LibreChat UI → AgentClient (API) → BackgroundCortexService
                       │                └─ Phase A detect (≤2s)
                       │                └─ Phase B execute (async)
                       ├→ pinned Feelings snapshot → dynamic instruction tail
                       ├→ spoken surface → shared feeling-expression + provider prompt
                       │                  └→ raw controls to TTS / sanitized visible text
                       │
                       ├→ SSE on_cortex_update → UI status cards
                       └→ BackgroundCortexFollowUpService → DB follow-up message
                       └→ detached EmotionalReactionService → FeelingState
```

### Key Backend Components
- Orchestration: `LibreChat/api/server/controllers/agents/client.js`
- Activation + execution: `LibreChat/api/server/services/BackgroundCortexService.js`
- Non-blocking follow-up + persistence: `LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- Follow-up suppression on user interruption: `LibreChat/api/server/services/ResponseController.js`
- Feelings state/decay/capsule: `LibreChat/packages/api/src/feelings/`
- Authenticated Feelings API: `LibreChat/api/server/routes/viventium/feelings.js`
- Detached reaction: `LibreChat/api/server/services/viventium/EmotionalReactionService.js`
- Spoken-surface prompt composition: `LibreChat/api/server/services/viventium/surfacePrompts.js`

### Key Frontend Components
- SSE buffering + cortex events: `LibreChat/client/src/hooks/SSE/useSSE.ts`, `LibreChat/client/src/hooks/SSE/useResumableSSE.ts`
- UI rendering: `LibreChat/client/src/components/Chat/Messages/Content/CortexCall.tsx`, `LibreChat/client/src/components/Chat/Messages/Content/CortexCallInfo.tsx`
- Follow-up polling: `LibreChat/client/src/hooks/Viventium/useCortexFollowUpPoll.ts`
- Export formatting: `LibreChat/client/src/hooks/Conversations/useExportConversation.ts`
- Feelings instrument: `LibreChat/client/src/components/Feelings/` at `/feelings`

## Feelings runtime

`AgentClient` loads and pins one lazily decayed per-user Feelings snapshot. The words-only capsule
uses private action-tendency phrases distinct from the UI scale adjectives and is appended after
stable/base/MCP instructions. `all_agents` also passes that capsule to background cortices and
GlassHive worker bootstrap bundles; `conscious_agent` omits those paths.

After a visible reply, `EmotionalReactionService` uses the configured always/classified/disabled
activation mode and a compact no-tool agent to return typed band operations. OpenAI runs request
JSON-object mode. The shared direct `executeCortex` wrapper validates and runs a declared
provider/model fallback after a recoverable primary failure; activated batch execution recognizes
that recovery and does not apply a second outer fallback. This gives direct callers such as the
Emotional Reaction Cortex the same recovery behavior as activated background cortices. The drawer,
structured telemetry, and persisted reaction health expose the requested primary/fallback, actual
route, fallback use, and primary error class. One invalid or still-unavailable typed response may
retry once, with every route bounded by the configured detached timeout. Version
matching, per-user serialization, bounded hashed stimulus idempotency, typed-delta rebasing, and an
atomic Mongo compare-and-set prevent lost/replayed reactions or overwritten user edits. Classifier
prose is discarded in favor of closed result codes. No reaction provider call is on the main response
path. Long public-safe telemetry envelopes are split into correlated, counted parts so the active text
formatter cannot truncate or ambiguously interleave route/version/model evidence.

Voice-capable requests compose the same private Feelings capsule with the registered shared
feeling-expression prompt and exactly one resolved TTS-provider dialect. The model appraises
expressive versus restrained delivery; runtime does not map band values to tags. Supported controls
remain in the provider-bound synthesis text, are removed from visible text, and are counted through
non-secret structural telemetry.

## Data Model (Agents)
Background agent configuration is stored on the main agent document:
```
Agent.background_cortices: Array<{
  agent_id: string,
  activation: {
    enabled: boolean,
    provider: string,
    model: string,
    prompt: string,
    confidence_threshold: number,
    cooldown_ms: number,
    max_history: number,
  }
}>
```
Sources:
- `LibreChat/packages/data-schemas/src/schema/agent.ts`
- `LibreChat/packages/data-provider/src/types/assistants.ts`
 - Internal content types (not UI): `LibreChat/packages/data-provider/src/types/runs.ts`

## Runtime Flow (Server)
1. `AgentClient.chatCompletion` builds the payload.
2. Previous background insights are extracted and injected into the system prompt.
3. Phase A activation detection runs with a 2s total time budget.
4. Activated agent metadata is injected into the system prompt, including one-line descriptions,
   activation scopes, and any matching main-agent direct-action scope keys.
5. UI activation cards are emitted via SSE (`on_cortex_update`).
6. Main agent response streams normally (non-blocking). If the activated scope is also covered by a
   connected main-agent direct-action surface, the main agent uses its own tools in Phase A and Phase
   B becomes supplemental.
7. Phase B executes activated agents in parallel, emitting brewing and terminal SSE updates.
   Terminal updates include visible insight, silent no-response success, and error states.
8. Completion data is persisted and merged onto the canonical assistant message. Silent
   no-response completion replaces the previous brewing part but renders no visible card.
9. A single follow-up message is generated (LLM-driven) if insights exist and the user has not sent new input.

## UI Label Sanitization
- Background agent display names are sanitized to remove internal jargon before being emitted to the UI.
- See `sanitizeCortexDisplayName` in `BackgroundCortexService.js`.

## SSE and Message ID Contract
LibreChat streams assistant messages into a placeholder id:
- UI placeholder: `uiMessageId = ${userMessageId}_`
- Canonical DB id: `responseMessageId`

Rules:
- SSE `on_cortex_update` must target `uiMessageId` during streaming.
- DB persistence and follow-up messages must target `responseMessageId`.

Implementation references:
- `client.js` emission block (uses `GenerationJobManager` for reliability).
- `useSSE.ts` / `useResumableSSE.ts` buffering and flush logic.

## Non-Blocking Follow-up
- Follow-up content is generated by the main agent LLM (not a background agent loop).
- Stored as a new assistant message with `metadata.viventium.type = "cortex_followup"`.
- Suppressed when a newer user input is detected (`ResponseController.lastUserInputTime`).

## Activation Cooldown
- Enforced in `BackgroundCortexService` via an in-memory cooldown map keyed by agent plus the
  structured request identity when available.
- Request identity uses user, conversation, and message ids rather than prompt text or provider
  labels. A live calendar check must not suppress a distinct email check from the same user just
  because both use the productivity cortices.
- Prevents duplicate activation work for the same request within `activation.cooldown_ms`.

## Activation Detection Payload
- Each activation check is an LLM classification that returns JSON:
  - `activate` (boolean), `confidence` (0..1), `reason` (short string).
- Detection receives the most recent messages capped by `activation.max_history`, but the latest
  human/user message is the only activation decision subject.
- Earlier turns are context only. They may resolve references in the latest message, but they must
  not reactivate a cortex just because an older activation-worthy user request still appears in
  history.
- The shared decision-subject rule is source-owned at
  `config.viventium.background_cortices.activation_subject_rule.prompt` and is injected into every
  cortex activation prompt before `## Latest User Intent` and `## Recent Conversation`.

## Export Formatting
- Background updates are converted to readable text during export in `useExportConversation.ts`.
- The export avoids raw JSON for `CORTEX_*` parts.
