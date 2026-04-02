<!-- === VIVENTIUM START ===
Document: Implementation Index
Added: 2026-01-09
=== VIVENTIUM END === -->

# Implementation Index (Viventium Changes)

This index lists the Viventium-specific changes and where they live.

## Background Agents (Server)
- Orchestration + prompt injection: `LibreChat/api/server/controllers/agents/client.js`
- Activation detection + execution + cooldown: `LibreChat/api/server/services/BackgroundCortexService.js`
- Follow-up persistence + LLM follow-up generation: `LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- Follow-up suppression when user interrupts: `LibreChat/api/server/services/ResponseController.js`

## Background Agents (Client)
- SSE buffering for cortex updates: `LibreChat/client/src/hooks/SSE/useSSE.ts`, `LibreChat/client/src/hooks/SSE/useResumableSSE.ts`
- Follow-up polling: `LibreChat/client/src/hooks/Viventium/useCortexFollowUpPoll.ts`
- Cortex UI rendering: `LibreChat/client/src/components/Chat/Messages/Content/CortexCall.tsx`, `LibreChat/client/src/components/Chat/Messages/Content/CortexCallInfo.tsx`
- Export formatting for cortex parts: `LibreChat/client/src/hooks/Conversations/useExportConversation.ts`

## Data Model / Types
- Agent schema (background_cortices): `LibreChat/packages/data-schemas/src/schema/agent.ts`
- ActivationConfig + BackgroundCortex types: `LibreChat/packages/data-provider/src/types/assistants.ts`
- Cortex content types: `LibreChat/packages/data-provider/src/types/runs.ts`

## Agent Builder (UI)
- Background agent config UI: `LibreChat/client/src/components/SidePanel/Agents/Viventium/BackgroundCorticesConfig.tsx`
- Advanced panel integration: `LibreChat/client/src/components/SidePanel/Agents/Advanced/AdvancedPanel.tsx`

## Voice Calls (LibreChat)
- Call session API: `LibreChat/api/server/routes/viventium/calls.js`
- Voice endpoints + auth: `LibreChat/api/server/routes/viventium/voice.js`
- Voice-mode prompt injection: `LibreChat/api/server/controllers/agents/client.js`
- Call session storage: `LibreChat/api/server/services/viventium/CallSessionService.js`
- Voice insight retrieval: `LibreChat/api/server/services/viventium/VoiceCortexInsightsService.js`
- Call button UI: `LibreChat/client/src/components/Viventium/CallButton.tsx`
- Chat header integration: `LibreChat/client/src/components/Chat/Header.tsx`

## Voice Gateway + Playground
- Voice gateway worker: `voice-gateway/worker.py`
- LibreChat LLM bridge: `voice-gateway/librechat_llm.py`
- SSE parsing + insight formatting: `voice-gateway/sse.py`
- Cartesia emotion segmentation + laughter normalization: `voice-gateway/cartesia_tts.py`
- Local whisper.cpp provider: `voice-gateway/pywhispercpp_provider.py`
- Playground deep-link token source: `agents-playground/src/pages/index.tsx`
- Playground token API: `agents-playground/src/pages/api/token.ts`
- Modern playground (agent-starter-react UI): `agent-starter-react`

## Tooling
- Full-stack launcher: `viventium-librechat-start.sh`
- LibreChat-only start: `LibreChat/scripts/viventium-start.sh`

## Voice Concurrency Control
- Voice sessions bypass concurrent limiter (configurable): `LibreChat/api/server/controllers/agents/request.js`

## Tests
- Background follow-up tests: `LibreChat/api/test/services/viventium/backgroundCortexFollowUpService.test.js`
- Voice insight service tests: `LibreChat/api/test/services/viventium/voiceCortexInsightsService.test.js`
- Cartesia TTS normalization tests: `voice-gateway/tests/test_cartesia_tts.py`
